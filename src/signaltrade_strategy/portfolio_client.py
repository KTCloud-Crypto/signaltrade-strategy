from dataclasses import dataclass

import httpx

from signaltrade_strategy.config import settings


class PortfolioUnavailable(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OpenPosition:
    subscription_id: int
    user_id: int
    mode: str
    volume: float
    average_buy_price: float


@dataclass(frozen=True, slots=True)
class StrategyCash:
    cash_balance: float
    reserved_amount: float
    available_cash: float


def get_strategy_cash(user_id: int, mode: str,
                      exclude_subscription_id: int | None = None) -> StrategyCash:
    if not settings.internal_service_token:
        raise PortfolioUnavailable("내부 서비스 토큰이 설정되지 않았습니다.")
    params: dict[str, str | int] = {"mode": mode}
    if exclude_subscription_id is not None:
        params["exclude_subscription_id"] = exclude_subscription_id
    try:
        response = httpx.get(
            f"{settings.portfolio_service_url.rstrip('/')}/internal/portfolio/users/{user_id}/strategy-cash",
            params=params,
            headers={"X-SignalTrade-Service-Token": settings.internal_service_token},
            timeout=settings.portfolio_service_timeout_seconds,
        )
    except httpx.HTTPError as error:
        raise PortfolioUnavailable("Portfolio 서비스에서 주문 가능 금액을 조회할 수 없습니다.") from error
    if response.status_code != 200:
        raise PortfolioUnavailable("Portfolio 서비스에서 주문 가능 금액을 조회할 수 없습니다.")
    return StrategyCash(**response.json())


def get_open_positions(market: str) -> list[OpenPosition]:
    if not settings.internal_service_token:
        raise PortfolioUnavailable("내부 서비스 토큰이 설정되지 않았습니다.")
    try:
        response = httpx.get(
            f"{settings.portfolio_service_url.rstrip('/')}/internal/portfolio/markets/{market}/open-positions",
            headers={"X-SignalTrade-Service-Token": settings.internal_service_token},
            timeout=settings.portfolio_service_timeout_seconds,
        )
    except httpx.HTTPError as error:
        raise PortfolioUnavailable("Portfolio 서비스에서 포지션을 조회할 수 없습니다.") from error
    if response.status_code != 200:
        raise PortfolioUnavailable("Portfolio 서비스에서 포지션을 조회할 수 없습니다.")
    return [OpenPosition(**item) for item in response.json()]
