import pytest
from pydantic import ValidationError

from signaltrade_strategy.schemas import StrategySubscriptionIn


def test_disable_accepts_legacy_zero_ratio():
    payload = StrategySubscriptionIn(enabled=False, invest_ratio=0)
    assert payload.enabled is False
    assert payload.invest_ratio == 0


def test_enabled_strategy_still_requires_ratio_of_at_least_one_percent():
    with pytest.raises(ValidationError, match="0.01 이상"):
        StrategySubscriptionIn(enabled=True, invest_ratio=0)
