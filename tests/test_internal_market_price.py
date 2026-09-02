from fastapi.testclient import TestClient

from signaltrade_strategy.config import settings
from signaltrade_strategy.main import app


def test_internal_market_price_requires_token_and_returns_price(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_token", "runtime-token")

    async def fake_price(market):
        assert market == "KRW-BTC"
        return 12345.0

    monkeypatch.setattr("signaltrade_strategy.api_internal.get_current_price", fake_price)
    client = TestClient(app)
    assert client.get("/internal/strategy/market-price/KRW-BTC").status_code == 401
    response = client.get(
        "/internal/strategy/market-price/krw-btc",
        headers={"X-SignalTrade-Service-Token": "runtime-token"},
    )
    assert response.status_code == 200
    assert response.json() == {"market": "KRW-BTC", "price": 12345.0}
