from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError

from signaltrade_strategy.config import settings
from signaltrade_strategy.database import SessionLocal
from signaltrade_strategy.evaluators import StrategyEvaluator, create_evaluator
from signaltrade_strategy.market_data import Candle, CandleBuilder, TradeTick, fetch_completed_minute_candles
from signaltrade_strategy.models.strategy import Strategy, SupportedMarket, UserStrategy
from signaltrade_strategy.models.strategy_signal import StrategyRuntime, StrategySignal
from signaltrade_strategy.strategy_events import enqueue_strategy_signal_created
from signaltrade_strategy.telemetry import STRATEGY_SIGNALS

logger = logging.getLogger(__name__)
OFFICIAL_CANDLE_FETCH_ATTEMPTS = 4
OFFICIAL_CANDLE_RETRY_SECONDS = 0.5
OFFICIAL_CANDLE_RECOVERY_COUNT = 10


@dataclass(frozen=True, slots=True)
class StrategyDefinition:
    id: int
    code: str
    market: str
    timeframe_minutes: int
    parameters: dict


def _active_definitions() -> list[StrategyDefinition]:
    with SessionLocal() as db:
        rows = (db.query(Strategy, SupportedMarket.code, UserStrategy.timeframe_minutes)
                .join(UserStrategy, UserStrategy.strategy_id == Strategy.id)
                .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
                .filter(Strategy.enabled.is_(True), UserStrategy.enabled.is_(True))
                .distinct().all())
        return [StrategyDefinition(s.id, s.code, market, timeframe, dict(s.parameters or {}))
                for s, market, timeframe in rows]


def _save_evaluation(definition: StrategyDefinition, candle: Candle,
                     action: str | None, metrics: dict[str, float]) -> int | None:
    with SessionLocal() as db:
        try:
            candle_time = datetime.utcfromtimestamp(candle.open_time_ms / 1000)
            runtime = (db.query(StrategyRuntime).filter_by(
                strategy_id=definition.id, market=definition.market,
                timeframe_minutes=definition.timeframe_minutes).first())
            values = dict(candle_open_time=candle_time, close_price=candle.close,
                          metrics=metrics, action=action, evaluated_at=datetime.utcnow())
            if runtime is None:
                db.add(StrategyRuntime(strategy_id=definition.id, market=candle.market,
                                       timeframe_minutes=definition.timeframe_minutes, **values))
            else:
                for name, value in values.items():
                    setattr(runtime, name, value)
            if action is None:
                db.commit()
                return None
            signal = StrategySignal(strategy_id=definition.id, market=candle.market,
                                    timeframe_minutes=definition.timeframe_minutes,
                                    action=action, source="engine", candle_open_time=candle_time,
                                    close_price=candle.close, metrics=metrics)
            db.add(signal)
            enqueue_strategy_signal_created(db, signal)
            db.commit()
            return signal.id
        except IntegrityError:
            db.rollback()
            return None


class StrategyEngine:
    """Strategy-owned candle evaluation; execution/risk exits remain service boundaries."""

    def __init__(self):
        self._definitions: dict[tuple[str, str, int], StrategyDefinition] = {}
        self._evaluators: dict[tuple[str, str, int], StrategyEvaluator] = {}
        self._builders: dict[int, CandleBuilder] = {}
        self._last_processed_candle: dict[tuple[str, str, int], int] = {}

    async def refresh(self) -> None:
        definitions = await asyncio.to_thread(_active_definitions)
        desired = {(x.code, x.market, x.timeframe_minutes): x for x in definitions}
        for key in set(self._definitions) - set(desired):
            self._definitions.pop(key, None); self._evaluators.pop(key, None)
            self._last_processed_candle.pop(key, None)
        for key, definition in desired.items():
            if self._definitions.get(key) == definition:
                continue
            evaluator = create_evaluator(definition.code, definition.parameters)
            candles = await fetch_completed_minute_candles(
                definition.market, definition.timeframe_minutes, evaluator.required_history)
            evaluator.warmup(candles)
            self._definitions[key] = definition; self._evaluators[key] = evaluator
            self._last_processed_candle[key] = candles[-1].open_time_ms if candles else -1
            self._builders.setdefault(definition.timeframe_minutes,
                                      CandleBuilder(definition.timeframe_minutes, self.on_candle_close))

    async def on_trade(self, tick: TradeTick) -> None:
        for builder in tuple(self._builders.values()):
            await builder.on_trade(tick)

    async def _official(self, candidate: Candle) -> list[Candle]:
        for attempt in range(OFFICIAL_CANDLE_FETCH_ATTEMPTS):
            try:
                candles = await fetch_completed_minute_candles(
                    candidate.market, candidate.interval_minutes, OFFICIAL_CANDLE_RECOVERY_COUNT)
            except Exception:
                candles = []
            if any(x.open_time_ms == candidate.open_time_ms for x in candles):
                return sorted((x for x in candles if x.open_time_ms <= candidate.open_time_ms),
                              key=lambda x: x.open_time_ms)
            if attempt + 1 < OFFICIAL_CANDLE_FETCH_ATTEMPTS:
                await asyncio.sleep(OFFICIAL_CANDLE_RETRY_SECONDS)
        return []

    async def on_candle_close(self, candle: Candle) -> None:
        keys = [key for key, definition in self._definitions.items()
                if definition.market == candle.market
                and definition.timeframe_minutes == candle.interval_minutes]
        if not keys:
            return
        official = await self._official(candle)
        for key in keys:
            definition, evaluator = self._definitions.get(key), self._evaluators.get(key)
            if definition is None or evaluator is None:
                continue
            for item in official:
                if item.open_time_ms <= self._last_processed_candle.get(key, -1):
                    continue
                result = evaluator.update(item); self._last_processed_candle[key] = item.open_time_ms
                if result is None:
                    continue
                action = result.action if item.open_time_ms == candle.open_time_ms else None
                signal_id = await asyncio.to_thread(_save_evaluation, definition, item,
                                                    action, result.metrics)
                if action and signal_id:
                    STRATEGY_SIGNALS.labels(definition.code, definition.market, action, "strategy").inc()
                    logger.info("Strategy signal queued: signal_id=%s", signal_id)

    async def refresh_loop(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await self.refresh()
            except Exception:
                logger.exception("Strategy refresh failed; retrying")
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=settings.strategy_refresh_seconds)
            except asyncio.TimeoutError:
                pass
