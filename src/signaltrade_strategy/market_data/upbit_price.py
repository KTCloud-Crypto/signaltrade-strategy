import asyncio
import time
from collections.abc import Callable
from typing import Any

import pyupbit

from signaltrade_strategy.telemetry import EXTERNAL_DURATION, EXTERNAL_REQUESTS


RETRY_COUNT = 2
RETRY_DELAY_SECONDS = 0.5


async def _observe_price(operation: str, callback: Callable[[], Any]) -> Any:
    started = time.perf_counter()
    try:
        result = await asyncio.get_running_loop().run_in_executor(None, callback)
    except Exception:
        EXTERNAL_REQUESTS.labels("upbit", operation, "error").inc()
        raise
    finally:
        EXTERNAL_DURATION.labels("upbit", operation).observe(time.perf_counter() - started)
    EXTERNAL_REQUESTS.labels("upbit", operation, "success").inc()
    return result


async def get_current_price(ticker: str) -> float:
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            result = await _observe_price(
                "get_current_price", lambda: pyupbit.get_current_price(ticker)
            )
            if result is not None:
                return float(result)
            last_error = ValueError("empty current price response")
        except Exception as error:
            last_error = error
        if attempt < RETRY_COUNT:
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise ValueError(f"failed to fetch Upbit current price: {ticker}") from last_error


async def get_market_tickers(markets: list[str]) -> list[dict]:
    last_error: Exception | None = None
    for attempt in range(RETRY_COUNT + 1):
        try:
            result = await _observe_price(
                "get_market_tickers",
                lambda: pyupbit.get_current_price(markets, verbose=True),
            )
            return result or []
        except Exception as error:
            last_error = error
        if attempt < RETRY_COUNT:
            await asyncio.sleep(RETRY_DELAY_SECONDS)
    raise ValueError("failed to fetch Upbit market prices") from last_error
