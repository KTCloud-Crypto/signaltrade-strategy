from __future__ import annotations

import asyncio
import json
import logging
import time
from collections.abc import Awaitable, Callable

import websockets

from signaltrade_strategy.market_data.types import TradeTick
from signaltrade_strategy.telemetry import (
    MARKET_LAST_TICK,
    WEBSOCKET_CONNECTIONS,
    WEBSOCKET_RECONNECTS,
)

logger = logging.getLogger(__name__)
TradeCallback = Callable[[TradeTick], Awaitable[None]]


class UpbitTradeStream:
    """Maintain an Upbit public trade stream and emit normalized ticks."""

    def __init__(self, url: str, markets: list[str], on_trade: TradeCallback):
        if not markets:
            raise ValueError("at least one Upbit market is required")
        self._url = url
        self._markets = markets
        self._on_trade = on_trade

    def _subscription(self) -> str:
        return json.dumps(
            [
                {"ticket": f"signaltrade-{int(time.time())}"},
                {"type": "trade", "codes": self._markets, "is_only_realtime": True},
                {"format": "DEFAULT"},
            ]
        )

    async def run(self, stop_event: asyncio.Event) -> None:
        backoff_seconds = 1.0
        while not stop_event.is_set():
            try:
                async with websockets.connect(
                    self._url,
                    ping_interval=30,
                    ping_timeout=20,
                    close_timeout=5,
                    max_queue=1024,
                ) as websocket:
                    WEBSOCKET_CONNECTIONS.labels("upbit").set(1)
                    await websocket.send(self._subscription())
                    backoff_seconds = 1.0
                    logger.info("Upbit WebSocket connected: markets=%s", self._markets)
                    while not stop_event.is_set():
                        raw = await asyncio.wait_for(websocket.recv(), timeout=90)
                        data = json.loads(raw)
                        if data.get("type") != "trade":
                            continue
                        tick = TradeTick(
                            market=data["code"],
                            price=float(data["trade_price"]),
                            volume=float(data["trade_volume"]),
                            timestamp_ms=int(data["trade_timestamp"]),
                            sequential_id=data.get("sequential_id"),
                        )
                        MARKET_LAST_TICK.labels(tick.market).set(time.time())
                        await self._on_trade(tick)
            except asyncio.CancelledError:
                WEBSOCKET_CONNECTIONS.labels("upbit").set(0)
                raise
            except Exception as error:
                WEBSOCKET_CONNECTIONS.labels("upbit").set(0)
                WEBSOCKET_RECONNECTS.labels("upbit").inc()
                logger.warning(
                    "Upbit WebSocket disconnected: retry_in=%ss error=%s",
                    backoff_seconds,
                    error,
                )
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=backoff_seconds)
                except asyncio.TimeoutError:
                    pass
                backoff_seconds = min(backoff_seconds * 2, 30.0)
        WEBSOCKET_CONNECTIONS.labels("upbit").set(0)
