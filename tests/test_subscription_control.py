from sqlalchemy import insert

from fastapi.testclient import TestClient

from signaltrade_strategy.database import SessionLocal
from signaltrade_strategy.main import app
from signaltrade_strategy.models import Strategy, SupportedMarket, UserStrategy, user_table


def test_only_owned_subscription_is_paused() -> None:
    with SessionLocal() as db:
        db.execute(insert(user_table), [{"id": 1}, {"id": 2}])
        market = SupportedMarket(code="KRW-BTC", display_name="Bitcoin")
        strategy = Strategy(code="test", name="test", description="test", timeframe_minutes=1, parameters={})
        db.add_all([market, strategy])
        db.flush()
        owned = UserStrategy(user_id=1, strategy_id=strategy.id, market_id=market.id, mode="simulated", invest_ratio=0.1)
        other = UserStrategy(user_id=2, strategy_id=strategy.id, market_id=market.id, mode="simulated", invest_ratio=0.1)
        db.add_all([owned, other])
        db.commit()

        response = TestClient(app).post(
            "/internal/strategy/subscriptions/pause",
            json={"user_id": 1, "subscription_ids": [owned.id, other.id], "paused": True},
        )
        assert response.status_code == 200
        assert response.json() == {"updated": 1}
        db.refresh(owned)
        db.refresh(other)
        assert owned.paused is True
        assert other.paused is False
