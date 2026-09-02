from datetime import datetime

from signaltrade_strategy.models.strategy import Strategy
from signaltrade_strategy.models.strategy_signal import StrategySignal
from signaltrade_strategy.strategy_events import enqueue_strategy_signal_created


def test_signal_and_outbox_are_created_in_same_session(db_session):
    strategy = Strategy(code="event-test", name="test", description="test",
                        timeframe_minutes=10, parameters={}, default_invest_ratio=0.1)
    db_session.add(strategy); db_session.flush()
    signal = StrategySignal(strategy_id=strategy.id, market="KRW-BTC",
                            timeframe_minutes=10, action="buy", source="engine",
                            candle_open_time=datetime(2026, 1, 1), close_price=100.0,
                            metrics={"sma": 99.0})
    db_session.add(signal)
    outbox = enqueue_strategy_signal_created(db_session, signal)
    db_session.commit()
    assert outbox.message_type == "StrategySignalCreated"
    assert outbox.payload["signal_id"] == signal.id
    assert outbox.idempotency_key == f"strategy-signal:{signal.id}"
