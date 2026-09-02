import hmac

from pydantic import BaseModel
from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from signaltrade_strategy.database import get_db
from signaltrade_strategy.config import settings
from signaltrade_strategy.market_data import get_current_price
from signaltrade_strategy.models.strategy import UserStrategy
from signaltrade_strategy.subscription_control import set_subscriptions_paused


def require_internal_service_token(
    service_token: str | None = Header(default=None, alias="X-SignalTrade-Service-Token"),
) -> None:
    expected = settings.internal_service_token
    if not expected or not service_token or not hmac.compare_digest(service_token, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="유효한 내부 서비스 토큰이 필요합니다.")


router = APIRouter(prefix="/internal/strategy", tags=["Strategy Internal"],
                   dependencies=[Depends(require_internal_service_token)])


class PauseSubscriptionsCommand(BaseModel):
    user_id: int
    subscription_ids: list[int]
    paused: bool


@router.post("/subscriptions/pause")
def pause_subscriptions(command: PauseSubscriptionsCommand, db: Session = Depends(get_db)) -> dict[str, int]:
    return {
        "updated": set_subscriptions_paused(
            db,
            user_id=command.user_id,
            subscription_ids=command.subscription_ids,
            paused=command.paused,
        )
    }


@router.post("/users/{user_id}/disable-live-subscriptions")
def disable_live_subscriptions(user_id: int, db: Session = Depends(get_db)) -> dict[str, int]:
    updated = (
        db.query(UserStrategy)
        .filter(UserStrategy.user_id == user_id, UserStrategy.mode == "live")
        .update({UserStrategy.enabled: False}, synchronize_session=False)
    )
    db.commit()
    return {"updated": updated}


class MarketPriceResponse(BaseModel):
    market: str
    price: float


@router.get("/market-price/{market}", response_model=MarketPriceResponse)
async def current_market_price(market: str) -> MarketPriceResponse:
    normalized = market.upper()
    if normalized not in settings.watch_market_list:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail="지원하지 않는 종목입니다.")
    try:
        price = await get_current_price(normalized)
    except ValueError as error:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            detail="현재가를 조회할 수 없습니다.") from error
    return MarketPriceResponse(market=normalized, price=price)
