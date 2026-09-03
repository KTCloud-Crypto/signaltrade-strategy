from sqlalchemy import Column, Integer, String, Table

from signaltrade_strategy.database import Base
from signaltrade_strategy.models.strategy import (
    Strategy, StrategySubscriptionEvent, SupportedMarket, UserStrategy,
)
from signaltrade_strategy.models.strategy_signal import StrategyRuntime, StrategySignal
from signaltrade_strategy.models.message_outbox import MessageOutbox

# Foreign-key-only compatibility table. Identity remains the WRITE owner.
user_table = Table("user", Base.metadata, Column("id", Integer, primary_key=True))
strategy_execution_table = Table(
    "strategy_execution",
    Base.metadata,
    Column("id", Integer, primary_key=True),
    Column("signal_id", Integer),
    Column("user_id", Integer, nullable=False),
    Column("user_strategy_id", Integer, nullable=False),
    Column("mode", String(16), nullable=False),
)

__all__ = ["MessageOutbox", "Strategy", "StrategyRuntime", "StrategySignal", "StrategySubscriptionEvent", "SupportedMarket", "UserStrategy", "strategy_execution_table"]
