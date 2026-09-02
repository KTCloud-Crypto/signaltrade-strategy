import asyncio
import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from signaltrade_strategy.market_data import history, upbit_price
from signaltrade_strategy.market_data.stream import UpbitTradeStream


async def _ignore_tick(_tick):
    return None


def test_stream_requires_market_and_builds_subscription():
    with pytest.raises(ValueError):
        UpbitTradeStream("wss://example.test", [], _ignore_tick)

    stream = UpbitTradeStream("wss://example.test", ["KRW-BTC", "KRW-ETH"], _ignore_tick)
    subscription = json.loads(stream._subscription())
    assert subscription[1] == {
        "type": "trade",
        "codes": ["KRW-BTC", "KRW-ETH"],
        "is_only_realtime": True,
    }


def test_history_excludes_open_candle_and_sorts(monkeypatch):
    now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
    rows = [
        {
            "candle_date_time_utc": now.replace(tzinfo=None).isoformat(),
            "opening_price": 3,
            "high_price": 4,
            "low_price": 2,
            "trade_price": 3.5,
            "candle_acc_trade_volume": 10,
        },
        {
            "candle_date_time_utc": (now - timedelta(minutes=2)).replace(tzinfo=None).isoformat(),
            "opening_price": 1,
            "high_price": 2,
            "low_price": 0.5,
            "trade_price": 1.5,
            "candle_acc_trade_volume": 8,
        },
        {
            "candle_date_time_utc": (now - timedelta(minutes=1)).replace(tzinfo=None).isoformat(),
            "opening_price": 2,
            "high_price": 3,
            "low_price": 1,
            "trade_price": 2.5,
            "candle_acc_trade_volume": 9,
        },
    ]

    class FakeClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, path, params):
            request = httpx.Request("GET", f"https://example.test{path}", params=params)
            return httpx.Response(200, request=request, json=rows)

    monkeypatch.setattr(history.httpx, "AsyncClient", FakeClient)
    candles = asyncio.run(history.fetch_completed_minute_candles("KRW-BTC", 1, 2))
    assert [candle.close for candle in candles] == [1.5, 2.5]


def test_current_price_runs_adapter_off_event_loop(monkeypatch):
    monkeypatch.setattr(upbit_price.pyupbit, "get_current_price", lambda ticker: 123.45)
    assert asyncio.run(upbit_price.get_current_price("KRW-BTC")) == 123.45


def test_market_tickers_returns_empty_result(monkeypatch):
    monkeypatch.setattr(upbit_price.pyupbit, "get_current_price", lambda *_args, **_kwargs: None)
    assert asyncio.run(upbit_price.get_market_tickers(["KRW-BTC"])) == []
