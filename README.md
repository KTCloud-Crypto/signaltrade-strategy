# signaltrade-strategy

SignalTrade의 Strategy API, 전략 Worker 및 Market Data 처리를 소유합니다.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
```

API 실행:

```sh
.venv/bin/uvicorn signaltrade_strategy.main:app --host 0.0.0.0 --port 8000
```

기준: `KTCloud-Crypto` `feat/132`
`013107ae8ddd08bed02d88db89af7eeb0cf65bba`
Trading의 수동 청산 시세 조회를 위해 내부 토큰으로 보호된 현재가 API를 제공합니다.
Market Data 조회 책임은 Strategy에 유지하고 Trading에는 가격 조회 구현을 복사하지
않습니다.

