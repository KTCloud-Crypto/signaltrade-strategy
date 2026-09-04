import httpx

from signaltrade_strategy.config import settings
from signaltrade_strategy.portfolio_client import get_strategy_cash


def test_strategy_cash_client_sends_mode_and_exclusion(monkeypatch):
    monkeypatch.setattr(settings, "internal_service_token", "runtime-token")

    def fake_get(url, **kwargs):
        assert url.endswith("/internal/portfolio/users/7/strategy-cash")
        assert kwargs["params"] == {"mode": "simulated", "exclude_subscription_id": 11}
        return httpx.Response(200, json={"cash_balance": 100_000, "reserved_amount": 40_000,
                                         "available_cash": 59_970})

    monkeypatch.setattr(httpx, "get", fake_get)
    result = get_strategy_cash(7, "simulated", 11)
    assert result.available_cash == 59_970
