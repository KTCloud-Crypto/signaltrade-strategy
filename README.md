# SignalTrade Strategy

지원 종목의 시세를 읽고 사용자 전략을 평가해 매수·매도 신호를 만드는 서비스입니다. API는 전략 설정 화면을 제공하고, Worker는 정해진 주기로 전략을 계산합니다.

## 주요 책임

- 지원 종목과 전략 카탈로그 제공
- 사용자별 전략 구독, 주문 예산, 분봉 설정 관리
- Upbit REST·WebSocket 기반 시세 처리
- 전략 runtime 값과 매수·매도 신호 기록
- 테스트 신호와 수동 청산에 필요한 현재가 제공

## 디렉터리

```text
src/signaltrade_strategy/
  api_public.py       전략·종목·신호 API
  worker.py           주기적 전략 평가 Worker
  market_data/        Upbit 시세·캔들 처리
  models/             전략·구독·신호 모델
  strategy_events.py  신호 Outbox 기록
tests/                계산, 구독, API 계약 테스트
```

## 다른 서비스와 통신

Frontend는 전략 목록, 활성 전략, 구독 이력, 신호를 HTTP로 조회합니다. Worker가 신호를 확정하면 같은 DB 트랜잭션에 Outbox를 기록합니다.

```text
Strategy Worker → StrategySignal + Outbox
               → Messaging → Trading Queue
               → Trading Worker
```

Trading은 내부 API로 현재가를 조회할 수 있지만, 시세 수집 구현을 직접 복사하지 않습니다.

## 로컬 확인

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
.venv/bin/pytest
.venv/bin/uvicorn signaltrade_strategy.main:app --host 0.0.0.0 --port 8000
```

Worker는 kind Deployment에서 별도 Pod로 실행됩니다.
