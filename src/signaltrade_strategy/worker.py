from __future__ import annotations

import asyncio
import logging
import signal
import threading

from prometheus_client import start_http_server

import signaltrade_strategy.models  # noqa: F401
from signaltrade_strategy.catalog import seed_strategy_catalog
from signaltrade_strategy.config import settings
from signaltrade_strategy.database import SessionLocal
from signaltrade_strategy.engine import StrategyEngine
from signaltrade_strategy.market_data import TradeTick, UpbitTradeStream
from signaltrade_strategy.sqs import QueueMessage, SqsQueueAdapter
from signaltrade_strategy.strategy_commands import apply_allocation_changed

logger = logging.getLogger(__name__)


def initialize_database() -> None:
    with SessionLocal() as db:
        seed_strategy_catalog(db)


async def initialize_until_ready(stop_event: asyncio.Event) -> StrategyEngine | None:
    while not stop_event.is_set():
        try:
            await asyncio.to_thread(initialize_database)
            engine = StrategyEngine()
            await engine.refresh()
            return engine
        except Exception:
            logger.exception("Strategy dependencies unavailable; retrying startup")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=2)
            except asyncio.TimeoutError:
                pass
    return None


def _process_strategy_command(queue: SqsQueueAdapter, message: QueueMessage) -> None:
    result = apply_allocation_changed(message.envelope)
    queue.acknowledge(message)
    logger.info("Strategy allocation updated: execution_id=%s user_strategy_id=%s updated=%s",
                result.execution_id, result.user_strategy_id, result.updated)


def run_strategy_command_consumer(stop_event: threading.Event) -> None:
    queue = SqsQueueAdapter.from_settings(settings.sqs_strategy_command_queue_name)
    while not stop_event.is_set():
        try:
            for message in queue.receive(
                max_messages=10, wait_time_seconds=5,
                visibility_timeout=settings.sqs_strategy_visibility_timeout_seconds,
            ):
                _process_strategy_command(queue, message)
        except Exception:
            logger.exception("Strategy command receive failed; retrying")
            stop_event.wait(1)


async def main() -> None:
    stop_event = asyncio.Event()
    command_stop_event = threading.Event()
    if settings.metrics_enabled:
        start_http_server(settings.worker_metrics_port)
    loop = asyncio.get_running_loop()
    for signal_name in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signal_name, stop_event.set)
    engine = await initialize_until_ready(stop_event)
    if engine is None:
        return
    stream = UpbitTradeStream(settings.upbit_ws_url, settings.watch_market_list, engine.on_trade)
    tasks = [
        asyncio.create_task(stream.run(stop_event), name="upbit-trade-stream"),
        asyncio.create_task(engine.refresh_loop(stop_event), name="strategy-refresh"),
    ]
    command_thread = threading.Thread(target=run_strategy_command_consumer,
                                      args=(command_stop_event,), daemon=True)
    command_thread.start()
    logger.info("Strategy worker started")
    await stop_event.wait()
    command_stop_event.set()
    await asyncio.gather(*tasks, return_exceptions=True)
    command_thread.join(timeout=6)


def run() -> None:
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())


if __name__ == "__main__":
    run()
