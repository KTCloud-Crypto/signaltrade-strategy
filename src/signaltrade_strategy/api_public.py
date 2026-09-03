from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from signaltrade_strategy.config import settings
from signaltrade_strategy.database import get_db
from signaltrade_strategy.identity_client import AuthenticatedUser, get_current_user
from signaltrade_strategy.market_data.upbit_price import get_current_price, get_market_tickers
from signaltrade_strategy.models import (
    Strategy, StrategyRuntime, StrategySignal, StrategySubscriptionEvent, SupportedMarket,
    UserStrategy,
)
from signaltrade_strategy.schemas import (
    MarketTickerOut, ReservedStrategyOut, StrategyOut, StrategySignalOut,
    StrategySubscriptionEventOut, StrategySubscriptionIn, StrategyTestSignalIn,
    StrategyTestSignalOut, SupportedMarketOut,
)
from signaltrade_strategy.strategy_events import enqueue_strategy_signal_created

router = APIRouter(prefix="/strategies", tags=["Strategies"])
ALLOWED_TIMEFRAMES = [1, 3, 5, 10, 15, 30, 60, 240]


def _position_volume(db: Session, subscription_id: int, mode: str) -> float:
    statuses = ("simulated_success",) if mode == "simulated" else ("success", "partially_filled")
    rows = db.execute(text("""
        SELECT se.action, COALESCE(se.executed_volume, 0) AS volume
        FROM strategy_execution se LEFT JOIN strategy_signal ss ON ss.id = se.signal_id
        WHERE se.user_strategy_id = :subscription_id AND se.mode = :mode
          AND se.status = ANY(:statuses) AND COALESCE(ss.source, '') <> 'external_sync'
        ORDER BY se.created_at, se.id
    """), {"subscription_id": subscription_id, "mode": mode, "statuses": list(statuses)}).mappings()
    volume = sum(float(row["volume"]) * (1 if row["action"] == "buy" else -1) for row in rows)
    if mode == "live":
        deducted = db.execute(text("""
            SELECT COALESCE(SUM(volume), 0) FROM position_sync_adjustment
            WHERE user_strategy_id=:subscription_id AND action IN ('deduct', 'sell')
        """), {"subscription_id": subscription_id}).scalar_one()
        volume -= float(deducted)
    return max(volume, 0.0)


def _out(strategy: Strategy, market: SupportedMarket, subscription: UserStrategy | None,
         runtime: StrategyRuntime | None = None, has_position: bool = False) -> StrategyOut:
    return StrategyOut(
        id=strategy.id, code=strategy.code, name=strategy.name, description=strategy.description,
        market=market.code, market_name=market.display_name,
        timeframe_minutes=strategy.timeframe_minutes, parameters=strategy.parameters or {},
        default_invest_ratio=strategy.default_invest_ratio,
        selected=bool(subscription and subscription.enabled), paused=bool(subscription and subscription.paused),
        has_open_position=has_position, invest_ratio=subscription.invest_ratio if subscription else 0.0,
        allocated_amount=subscription.allocated_amount if subscription else None,
        allocation_mode=subscription.allocation_mode if subscription else "ratio", available_cash=None,
        stop_loss_rate=subscription.stop_loss_rate if subscription else None,
        take_profit_rate=subscription.take_profit_rate if subscription else None,
        selected_timeframe_minutes=subscription.timeframe_minutes if subscription else 0,
        allowed_timeframes=ALLOWED_TIMEFRAMES,
        last_evaluated_at=runtime.evaluated_at if runtime else None,
        last_close_price=runtime.close_price if runtime else None,
        last_metrics=runtime.metrics if runtime else {}, last_action=runtime.action if runtime else None,
    )


def _market(db: Session, code: str) -> SupportedMarket:
    item = db.query(SupportedMarket).filter(SupportedMarket.code == code.upper(),
                                            SupportedMarket.enabled.is_(True)).first()
    if item is None:
        raise HTTPException(404, "지원하지 않는 종목입니다.")
    return item


@router.get("", response_model=list[StrategyOut])
def list_strategies(mode: Literal["simulated", "live"] = Query("simulated"),
                    market: str = Query("KRW-BTC"), db: Session = Depends(get_db),
                    user: AuthenticatedUser = Depends(get_current_user)):
    selected_market = _market(db, market)
    strategies = db.query(Strategy).filter(Strategy.enabled.is_(True),
                                            Strategy.code != "manual_hold_v1").order_by(Strategy.id).all()
    subscriptions = {item.strategy_id: item for item in db.query(UserStrategy).filter_by(
        user_id=user.id, market_id=selected_market.id, mode=mode).all()}
    result = []
    for strategy in strategies:
        sub = subscriptions.get(strategy.id)
        timeframe = sub.timeframe_minutes if sub else strategy.timeframe_minutes
        runtime = db.query(StrategyRuntime).filter_by(strategy_id=strategy.id,
            market=selected_market.code, timeframe_minutes=timeframe).first()
        result.append(_out(strategy, selected_market, sub, runtime,
                           bool(sub and _position_volume(db, sub.id, mode) > 0)))
    return result


@router.get("/active", response_model=list[StrategyOut])
def list_active(mode: Literal["simulated", "live"] = Query("simulated"),
                db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.query(UserStrategy, Strategy, SupportedMarket).join(Strategy).join(SupportedMarket).filter(
        UserStrategy.user_id == user.id, UserStrategy.mode == mode,
        Strategy.code != "manual_hold_v1").all()
    result = []
    for sub, strategy, market in rows:
        has_position = _position_volume(db, sub.id, mode) > 0
        if sub.enabled or has_position:
            runtime = db.query(StrategyRuntime).filter_by(strategy_id=strategy.id, market=market.code,
                timeframe_minutes=sub.timeframe_minutes).first()
            result.append(_out(strategy, market, sub, runtime, has_position))
    return result


@router.get("/markets", response_model=list[SupportedMarketOut])
def markets(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)):
    return db.query(SupportedMarket).filter(SupportedMarket.enabled.is_(True)).order_by(
        SupportedMarket.sort_order, SupportedMarket.id).all()


@router.get("/markets/tickers", response_model=list[MarketTickerOut])
async def tickers(db: Session = Depends(get_db), _: AuthenticatedUser = Depends(get_current_user)):
    names = {item.code: item.display_name for item in db.query(SupportedMarket).filter(
        SupportedMarket.enabled.is_(True)).all()}
    return [MarketTickerOut(market=item["market"], display_name=names.get(item["market"], item["market"]),
        price=float(item.get("trade_price") or 0), change_price=float(item.get("signed_change_price") or 0),
        change_rate=float(item.get("signed_change_rate") or 0) * 100,
        trade_value_24h=float(item.get("acc_trade_price_24h") or 0))
        for item in await get_market_tickers(settings.watch_market_list) if item.get("market")]


@router.get("/allocation")
def allocation(mode: Literal["simulated", "live"] = Query("simulated"), db: Session = Depends(get_db),
               user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.query(UserStrategy).join(Strategy).filter(UserStrategy.user_id == user.id,
        UserStrategy.mode == mode, UserStrategy.enabled.is_(True), Strategy.code != "manual_hold_v1").all()
    return {"total_ratio": sum(item.invest_ratio for item in rows), "active_count": len(rows)}


@router.get("/subscription-events", response_model=list[StrategySubscriptionEventOut])
def subscription_events(mode: Literal["simulated", "live"] = Query("simulated"),
                        db: Session = Depends(get_db), user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.query(StrategySubscriptionEvent, Strategy, SupportedMarket).join(Strategy).join(
        SupportedMarket).filter(StrategySubscriptionEvent.user_id == user.id,
        StrategySubscriptionEvent.mode == mode).order_by(StrategySubscriptionEvent.created_at.desc()).limit(100).all()
    return [StrategySubscriptionEventOut(id=e.id, strategy_name=s.name, market=m.code,
        market_name=m.display_name, action=e.action, timeframe_minutes=e.timeframe_minutes,
        created_at=e.created_at) for e, s, m in rows]


@router.get("/signals", response_model=list[StrategySignalOut])
def signals(mode: Literal["simulated", "live"] = Query("simulated"), db: Session = Depends(get_db),
            user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.query(StrategySignal, Strategy).join(Strategy).join(UserStrategy,
        (UserStrategy.strategy_id == StrategySignal.strategy_id) &
        (UserStrategy.timeframe_minutes == StrategySignal.timeframe_minutes)).join(
        SupportedMarket, SupportedMarket.id == UserStrategy.market_id).filter(
        UserStrategy.user_id == user.id, UserStrategy.mode == mode, UserStrategy.enabled.is_(True),
        SupportedMarket.code == StrategySignal.market, StrategySignal.source != "external_sync",
        Strategy.code != "manual_hold_v1").order_by(StrategySignal.created_at.desc()).limit(50).all()
    return [StrategySignalOut(id=sig.id, strategy_name=s.name, strategy_code=s.code,
        market=sig.market, timeframe_minutes=sig.timeframe_minutes, action=sig.action, source=sig.source,
        close_price=sig.close_price, metrics=sig.metrics or {}, candle_open_time=sig.candle_open_time,
        created_at=sig.created_at) for sig, s in rows]


@router.put("/{strategy_id}/subscription", response_model=StrategyOut)
def update_subscription(strategy_id: int, payload: StrategySubscriptionIn, request: Request,
                        mode: Literal["simulated", "live"] = Query("simulated"),
                        market: str = Query("KRW-BTC"), db: Session = Depends(get_db),
                        user: AuthenticatedUser = Depends(get_current_user)):
    if payload.enabled and mode == "live" and not user.live_trading_enabled:
        raise HTTPException(409, "실전투자를 사용하려면 먼저 Upbit API Key를 연결해 주세요.")
    strategy = db.query(Strategy).filter_by(id=strategy_id, enabled=True).first()
    if strategy is None:
        raise HTTPException(404, "전략을 찾을 수 없습니다.")
    selected_market = _market(db, market)
    sub = db.query(UserStrategy).filter_by(user_id=user.id, strategy_id=strategy_id,
        market_id=selected_market.id, mode=mode).first()
    if payload.enabled and payload.timeframe_minutes is None:
        raise HTTPException(422, "전략을 활성화하려면 분봉을 설정한 후 저장해 주세요.")
    if payload.enabled and payload.invest_ratio is None and payload.invest_amount is None:
        raise HTTPException(422, "전략을 활성화하려면 투자 비율 또는 주문 금액을 설정해 주세요.")
    was_enabled = bool(sub and sub.enabled)
    if sub is None:
        sub = UserStrategy(user_id=user.id, strategy_id=strategy.id, market_id=selected_market.id,
            mode=mode, invest_ratio=payload.invest_ratio or strategy.default_invest_ratio,
            allocated_amount=payload.invest_amount, allocation_mode="amount" if payload.invest_amount else "ratio",
            timeframe_minutes=payload.timeframe_minutes or strategy.timeframe_minutes,
            stop_loss_rate=payload.stop_loss_rate or None, take_profit_rate=payload.take_profit_rate or None,
            enabled=payload.enabled)
        db.add(sub)
    else:
        if _position_volume(db, sub.id, mode) > 0 and not payload.enabled and not payload.force_disable:
            raise HTTPException(409, "보유 중인 포지션을 먼저 매도한 후 전략 선택을 해제해 주세요.")
        sub.enabled = payload.enabled
        if payload.enabled and not was_enabled:
            sub.paused = False
        if payload.invest_ratio is not None: sub.invest_ratio = payload.invest_ratio
        if payload.invest_amount is not None:
            sub.allocated_amount, sub.allocation_mode = payload.invest_amount, "amount"
        if payload.timeframe_minutes is not None: sub.timeframe_minutes = payload.timeframe_minutes
        if "stop_loss_rate" in payload.model_fields_set: sub.stop_loss_rate = payload.stop_loss_rate or None
        if "take_profit_rate" in payload.model_fields_set: sub.take_profit_rate = payload.take_profit_rate or None
    if payload.enabled != was_enabled:
        db.add(StrategySubscriptionEvent(user_id=user.id, strategy_id=strategy.id,
            market_id=selected_market.id, mode=mode, action="start" if payload.enabled else "stop",
            timeframe_minutes=sub.timeframe_minutes))
    db.commit(); db.refresh(sub)
    runtime = db.query(StrategyRuntime).filter_by(strategy_id=strategy.id, market=selected_market.code,
        timeframe_minutes=sub.timeframe_minutes).first()
    return _out(strategy, selected_market, sub, runtime, _position_volume(db, sub.id, mode) > 0)


@router.post("/{strategy_id}/test-signal", response_model=StrategyTestSignalOut)
async def test_signal(strategy_id: int, payload: StrategyTestSignalIn, request: Request,
                      mode: Literal["simulated", "live"] = Query("simulated"),
                      market: str = Query("KRW-BTC"), db: Session = Depends(get_db),
                      user: AuthenticatedUser = Depends(get_current_user)):
    if settings.environment.lower() not in {"development", "local", "test"}:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "운영 환경에서는 사용할 수 없습니다.")
    strategy = db.get(Strategy, strategy_id); selected_market = _market(db, market)
    sub = db.query(UserStrategy).filter_by(user_id=user.id, strategy_id=strategy_id,
        market_id=selected_market.id, mode=mode, enabled=True).first()
    if strategy is None or sub is None: raise HTTPException(409, "먼저 전략을 선택해 주세요.")
    price = await get_current_price(selected_market.code)
    signal = StrategySignal(strategy_id=strategy.id, market=selected_market.code,
        timeframe_minutes=sub.timeframe_minutes, action=payload.action, source="test",
        candle_open_time=datetime.utcnow(), close_price=price, metrics={"test_price": price})
    db.add(signal); db.flush(); enqueue_strategy_signal_created(db, signal); db.commit(); db.refresh(signal)
    return StrategyTestSignalOut(signal_id=signal.id, execution_count=1, action=signal.action,
                                 market=signal.market, price=signal.close_price)


@router.get("/reserved", response_model=list[ReservedStrategyOut])
def reserved(mode: Literal["simulated", "live"] = Query("simulated"), db: Session = Depends(get_db),
             user: AuthenticatedUser = Depends(get_current_user)):
    rows = db.query(UserStrategy, Strategy, SupportedMarket).join(Strategy).join(SupportedMarket).filter(
        UserStrategy.user_id == user.id, UserStrategy.mode == mode, UserStrategy.enabled.is_(True),
        Strategy.code != "manual_hold_v1").all()
    return [ReservedStrategyOut(id=s.id, name=s.name, market=m.code, market_name=m.display_name,
        invest_ratio=sub.invest_ratio, allocated_amount=sub.allocated_amount,
        allocation_mode=sub.allocation_mode, timeframe_minutes=sub.timeframe_minutes)
        for sub, s, m in rows if _position_volume(db, sub.id, mode) <= 0]
