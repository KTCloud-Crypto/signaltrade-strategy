from sqlalchemy import Column, Integer, Table

from signaltrade_strategy.database import Base
from signaltrade_strategy.models.strategy import (
    Strategy, StrategySubscriptionEvent, SupportedMarket, UserStrategy,
)
from signaltrade_strategy.models.strategy_signal import StrategyRuntime, StrategySignal

# Foreign-key-only compatibility table. Identity remains the WRITE owner.
user_table = Table("user", Base.metadata, Column("id", Integer, primary_key=True))

__all__ = ["Strategy", "StrategyRuntime", "StrategySignal", "StrategySubscriptionEvent", "SupportedMarket", "UserStrategy"]

