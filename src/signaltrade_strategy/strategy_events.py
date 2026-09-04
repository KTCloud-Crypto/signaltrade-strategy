from sqlalchemy.orm import Session

from signaltrade_strategy.message_contract import MessageEnvelope
from signaltrade_strategy.models.message_outbox import MessageOutbox
from signaltrade_strategy.models.strategy_signal import StrategySignal


def enqueue_strategy_signal_created(
    db: Session,
    signal: StrategySignal,
    *,
    target_user_id: int | None = None,
    target_mode: str | None = None,
) -> MessageOutbox:
    db.flush()
    if signal.id is None:
        raise ValueError("StrategySignal must have an id before creating its event")
    signal_key = f"strategy-signal:{signal.id}"
    envelope = MessageEnvelope.create(
        message_type="StrategySignalCreated", producer="strategy",
        correlation_id=signal_key, idempotency_key=signal_key,
        payload={"signal_id": signal.id, "strategy_id": signal.strategy_id,
                 "market": signal.market, "timeframe_minutes": signal.timeframe_minutes,
                 "action": signal.action, "source": signal.source,
                 "candle_open_time": signal.candle_open_time.isoformat(),
                 "close_price": signal.close_price, "metrics": signal.metrics or {},
                 "target_user_id": target_user_id, "target_mode": target_mode},
    )
    outbox = MessageOutbox(
        message_id=str(envelope.message_id), message_type=envelope.message_type,
        correlation_id=envelope.correlation_id, producer=envelope.producer,
        schema_version=envelope.schema_version, idempotency_key=envelope.idempotency_key,
        payload=envelope.payload, occurred_at=envelope.occurred_at,
    )
    db.add(outbox)
    return outbox
