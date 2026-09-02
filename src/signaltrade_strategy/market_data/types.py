from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class TradeTick:
    market: str
    price: float
    volume: float
    timestamp_ms: int
    sequential_id: int | None

