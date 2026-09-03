from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class StrategyOut(BaseModel):
    id: int
    code: str
    name: str
    description: str
    market: str
    market_name: str
    timeframe_minutes: int
    parameters: dict[str, float | int]
    default_invest_ratio: float
    selected: bool
    paused: bool
    has_open_position: bool
    invest_ratio: float
    allocated_amount: float | None = None
    allocation_mode: Literal["ratio", "amount"] = "ratio"
    available_cash: float | None = None
    stop_loss_rate: float | None
    take_profit_rate: float | None
    selected_timeframe_minutes: int
    allowed_timeframes: list[int]
    last_evaluated_at: datetime | None = None
    last_close_price: float | None = None
    last_metrics: dict[str, float] = Field(default_factory=dict)
    last_action: str | None = None


class StrategySubscriptionIn(BaseModel):
    enabled: bool
    force_disable: bool = False
    invest_ratio: float | None = Field(default=None, ge=0.01, le=1.0)
    invest_amount: float | None = Field(default=None, ge=0)
    timeframe_minutes: Literal[1, 3, 5, 10, 15, 30, 60, 240] | None = None
    stop_loss_rate: float | None = Field(default=None, ge=0, le=1.0)
    take_profit_rate: float | None = Field(default=None, ge=0, le=1.0)


class SupportedMarketOut(BaseModel):
    code: str
    display_name: str


class MarketTickerOut(BaseModel):
    market: str
    display_name: str
    price: float
    change_price: float
    change_rate: float
    trade_value_24h: float


class StrategySignalOut(BaseModel):
    id: int
    strategy_name: str
    strategy_code: str
    market: str
    timeframe_minutes: int
    action: Literal["buy", "sell"]
    source: str
    close_price: float
    metrics: dict[str, float]
    candle_open_time: datetime
    created_at: datetime


class StrategySubscriptionEventOut(BaseModel):
    id: int
    strategy_name: str
    market: str
    market_name: str
    action: Literal["start", "stop"]
    timeframe_minutes: int
    created_at: datetime


class ReservedStrategyOut(BaseModel):
    id: int
    name: str
    market: str
    market_name: str
    invest_ratio: float
    allocated_amount: float | None
    allocation_mode: Literal["ratio", "amount"] = "ratio"
    timeframe_minutes: int


class StrategyTestSignalIn(BaseModel):
    action: Literal["buy", "sell"]


class StrategyTestSignalOut(BaseModel):
    signal_id: int
    execution_count: int
    action: str
    market: str
    price: float
