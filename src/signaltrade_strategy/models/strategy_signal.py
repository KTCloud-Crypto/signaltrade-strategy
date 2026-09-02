from datetime import datetime

from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, JSON, String, UniqueConstraint

from signaltrade_strategy.database import Base


class StrategySignal(Base):
    __tablename__ = "strategy_signal"
    __table_args__ = (UniqueConstraint("strategy_id", "market", "timeframe_minutes", "candle_open_time", "action", name="uq_strategy_signal_market_candle_action"),)
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market = Column(String(20), nullable=False, index=True)
    timeframe_minutes = Column(Integer, nullable=False, default=10)
    action = Column(String(8), nullable=False)
    source = Column(String(16), nullable=False, default="engine")
    candle_open_time = Column(DateTime, nullable=False)
    close_price = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class StrategyRuntime(Base):
    __tablename__ = "strategy_runtime"
    __table_args__ = (UniqueConstraint("strategy_id", "market", "timeframe_minutes", name="uq_strategy_runtime_market_timeframe"),)
    id = Column(Integer, primary_key=True, index=True)
    strategy_id = Column(Integer, ForeignKey("strategy.id"), nullable=False, index=True)
    market = Column(String(20), nullable=False)
    timeframe_minutes = Column(Integer, nullable=False)
    candle_open_time = Column(DateTime, nullable=False)
    close_price = Column(Float, nullable=False)
    metrics = Column(JSON, nullable=False, default=dict)
    action = Column(String(8), nullable=True)
    evaluated_at = Column(DateTime, nullable=False, default=datetime.utcnow)
