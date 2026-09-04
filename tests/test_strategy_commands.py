from sqlalchemy import insert

from signaltrade_strategy.message_contract import MessageEnvelope
from signaltrade_strategy.models import user_table
from signaltrade_strategy.models.strategy import Strategy, SupportedMarket, UserStrategy
from signaltrade_strategy.strategy_commands import apply_allocation_changed


def test_allocation_changed_updates_strategy_owned_subscription(db_session):
    db_session.execute(insert(user_table), {"id": 1})
    strategy = Strategy(code="command-test", name="test", description="test",
                        timeframe_minutes=10, parameters={}, default_invest_ratio=0.1)
    market = SupportedMarket(code="KRW-TEST", display_name="test")
    db_session.add_all([strategy, market]); db_session.flush()
    subscription = UserStrategy(user_id=1, strategy_id=strategy.id, market_id=market.id,
                                mode="simulated", invest_ratio=0.2,
                                timeframe_minutes=10, enabled=True)
    db_session.add(subscription); db_session.commit()
    envelope = MessageEnvelope.create(
        message_type="AllocationChanged", producer="trading",
        payload={"execution_id": 7, "user_strategy_id": subscription.id,
                 "allocated_amount": 12345.0},
    )
    result = apply_allocation_changed(envelope)
    db_session.expire_all()
    assert result.updated is True
    assert db_session.get(UserStrategy, subscription.id).allocated_amount == 12345.0
