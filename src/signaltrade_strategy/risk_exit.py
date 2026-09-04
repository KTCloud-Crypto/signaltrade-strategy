"""Evaluate user stop-loss and take-profit settings against open positions."""

import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.orm import Session

from signaltrade_strategy.models.strategy import Strategy, SupportedMarket, UserStrategy
from signaltrade_strategy.models.strategy_signal import StrategySignal
from signaltrade_strategy.portfolio_client import PortfolioUnavailable, get_open_positions
from signaltrade_strategy.strategy_events import enqueue_strategy_signal_created
from signaltrade_strategy.telemetry import STRATEGY_SIGNALS

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RiskExitSignal:
    signal_id: int
    user_id: int
    mode: str


def triggered_exit_source(
    average_buy_price: float,
    current_price: float,
    stop_loss_rate: float | None,
    take_profit_rate: float | None,
) -> str | None:
    if average_buy_price <= 0:
        return None
    return_rate = (current_price - average_buy_price) / average_buy_price
    if stop_loss_rate is not None and return_rate <= -stop_loss_rate:
        return "stop_loss"
    if take_profit_rate is not None and return_rate >= take_profit_rate:
        return "take_profit"
    return None


def create_triggered_exit_signals(
    db: Session, market: str, price: float
) -> list[RiskExitSignal]:
    try:
        positions = {item.subscription_id: item for item in get_open_positions(market)}
    except PortfolioUnavailable:
        logger.exception("Risk exit position lookup failed: market=%s", market)
        return []

    rows = (
        db.query(UserStrategy, Strategy)
        .join(Strategy, Strategy.id == UserStrategy.strategy_id)
        .join(SupportedMarket, SupportedMarket.id == UserStrategy.market_id)
        .filter(
            SupportedMarket.code == market,
            Strategy.enabled.is_(True),
            UserStrategy.enabled.is_(True),
        )
        .all()
    )
    triggered: list[RiskExitSignal] = []
    for subscription, strategy in rows:
        position = positions.get(subscription.id)
        if position is None or position.user_id != subscription.user_id:
            continue
        if position.mode != subscription.mode or position.volume <= 0:
            continue
        source = triggered_exit_source(
            position.average_buy_price,
            price,
            subscription.stop_loss_rate,
            subscription.take_profit_rate,
        )
        if source is None:
            continue
        return_rate = (price - position.average_buy_price) / position.average_buy_price
        signal = StrategySignal(
            strategy_id=strategy.id,
            market=market,
            timeframe_minutes=subscription.timeframe_minutes,
            action="sell",
            source=source,
            candle_open_time=datetime.utcnow(),
            close_price=price,
            metrics={
                "average_buy_price": position.average_buy_price,
                "return_rate": return_rate,
            },
        )
        db.add(signal)
        enqueue_strategy_signal_created(
            db,
            signal,
            target_user_id=subscription.user_id,
            target_mode=subscription.mode,
        )
        STRATEGY_SIGNALS.labels(strategy.code, market, "sell", source).inc()
        triggered.append(RiskExitSignal(signal.id, subscription.user_id, subscription.mode))
    db.commit()
    return triggered
