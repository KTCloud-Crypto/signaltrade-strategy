from datetime import datetime

from sqlalchemy import insert

from signaltrade_strategy.api_public import signals
from signaltrade_strategy.identity_client import AuthenticatedUser
from signaltrade_strategy.models import (
    Strategy,
    StrategySignal,
    SupportedMarket,
    UserStrategy,
    strategy_execution_table,
    user_table,
)


def test_signal_history_is_separated_by_actual_execution_mode(db_session) -> None:
    db_session.execute(insert(user_table), {"id": 1})
    market = SupportedMarket(code="KRW-BTC", display_name="Bitcoin")
    strategy = Strategy(
        code="sma_cross_v1",
        name="SMA",
        description="test",
        timeframe_minutes=1,
        parameters={},
    )
    db_session.add_all([market, strategy])
    db_session.flush()
    simulated = UserStrategy(
        user_id=1,
        strategy_id=strategy.id,
        market_id=market.id,
        mode="simulated",
        timeframe_minutes=1,
        invest_ratio=0.5,
        enabled=True,
    )
    live = UserStrategy(
        user_id=1,
        strategy_id=strategy.id,
        market_id=market.id,
        mode="live",
        timeframe_minutes=1,
        invest_ratio=0.0,
        allocated_amount=10_000,
        allocation_mode="amount",
        enabled=True,
    )
    db_session.add_all([simulated, live])
    db_session.flush()
    signal = StrategySignal(
        strategy_id=strategy.id,
        market="KRW-BTC",
        timeframe_minutes=1,
        action="buy",
        source="engine",
        candle_open_time=datetime.utcnow(),
        close_price=100.0,
        metrics={},
    )
    db_session.add(signal)
    db_session.flush()
    db_session.execute(insert(strategy_execution_table), {
        "id": 1,
        "signal_id": signal.id,
        "user_id": 1,
        "user_strategy_id": simulated.id,
        "mode": "simulated",
    })
    db_session.commit()

    user = AuthenticatedUser(
        id=1,
        username="tester",
        nickname="Tester",
        bot_enabled=False,
        execution_mode="simulated",
        live_trading_enabled=True,
    )
    assert [item.id for item in signals(mode="simulated", db=db_session, user=user)] == [signal.id]
    assert signals(mode="live", db=db_session, user=user) == []
