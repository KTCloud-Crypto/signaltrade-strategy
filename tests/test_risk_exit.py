from sqlalchemy import insert

from signaltrade_strategy.models import Strategy, SupportedMarket, UserStrategy, user_table
from signaltrade_strategy.models.message_outbox import MessageOutbox
from signaltrade_strategy.models.strategy_signal import StrategySignal
from signaltrade_strategy.portfolio_client import OpenPosition
from signaltrade_strategy.risk_exit import (
    create_triggered_exit_signals,
    triggered_exit_source,
)


def test_exit_boundaries() -> None:
    assert triggered_exit_source(100, 95, 0.05, 0.10) == "stop_loss"
    assert triggered_exit_source(100, 110, 0.05, 0.10) == "take_profit"
    assert triggered_exit_source(100, 103, 0.05, 0.10) is None


def test_stop_loss_creates_user_targeted_sell_signal(db_session, monkeypatch) -> None:
    db_session.execute(insert(user_table), {"id": 1})
    market = SupportedMarket(code="KRW-BTC", display_name="Bitcoin")
    strategy = Strategy(code="sma", name="SMA", description="test", timeframe_minutes=1,
                        parameters={})
    db_session.add_all([market, strategy])
    db_session.flush()
    subscription = UserStrategy(
        user_id=1, strategy_id=strategy.id, market_id=market.id, mode="simulated",
        invest_ratio=0.5, timeframe_minutes=1, stop_loss_rate=0.05,
        take_profit_rate=0.10, enabled=True,
    )
    db_session.add(subscription)
    db_session.flush()
    monkeypatch.setattr(
        "signaltrade_strategy.risk_exit.get_open_positions",
        lambda _market: [OpenPosition(subscription.id, 1, "simulated", 0.2, 100.0)],
    )

    created = create_triggered_exit_signals(db_session, "KRW-BTC", 95.0)

    assert len(created) == 1
    signal = db_session.query(StrategySignal).one()
    assert (signal.action, signal.source, signal.close_price) == ("sell", "stop_loss", 95.0)
    outbox = db_session.query(MessageOutbox).one()
    assert outbox.payload["target_user_id"] == 1
    assert outbox.payload["target_mode"] == "simulated"
