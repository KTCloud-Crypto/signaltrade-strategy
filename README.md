# SignalTrade Strategy

투자 전략의 설정과 실행 상태를 소유하고, Upbit 시세를 바탕으로 매수·매도 신호를 생성하는 서비스입니다. API는 사용자가 전략을 설정하는 기능을 제공하고 Worker는 활성 전략을 주기적으로 평가합니다.

## 주요 역할

- 지원 마켓과 사용할 수 있는 전략 목록 관리
- 사용자별 전략 활성화·비활성화와 구독 이력 관리
- 주문 예산, 분봉, 손절·익절 등 실행 설정 관리
- Upbit REST·WebSocket을 통한 시세와 캔들 데이터 처리
- 전략별 계산 상태와 마지막 평가 결과 저장
- 조건 충족 시 매수·매도 전략 신호 생성
- 테스트 신호와 수동 청산에 필요한 현재가 제공

Strategy는 **무엇을 사고팔지 판단**하지만 실제 주문은 실행하지 않습니다. 주문 가능 여부, 체결과 거래소 호출은 Trading이 담당합니다.

## Write 권한이 있는 테이블

- `supported_market`: 지원하는 거래 마켓
- `strategy`: 전략 종류와 기본 정보
- `user_strategy`: 사용자의 전략 설정과 활성 상태
- `strategy_runtime`: 전략 계산 중 유지되는 실행 상태
- `strategy_signal`: 생성된 매수·매도 신호
- `strategy_subscription_event`: 전략 활성화·해제 이력
- `message_outbox`: Trading에 전달할 신호 이벤트

사용자 원본 정보, 주문 실행과 거래 원장은 직접 수정하지 않습니다.

## HTTP 통신

Frontend에 전략 목록, 사용자 설정, 활성 전략, 구독 이력과 신호 조회 API를 제공합니다. 전략 평가 전에는 Portfolio 내부 HTTP API로 사용 가능한 현금과 열린 포지션을 확인해 현재 자산 상태를 반영합니다.

다른 서비스가 동일한 시세 수집 로직을 복제하지 않도록 필요한 현재가도 내부 API로 제공합니다.

## Queue 통신

전략 신호와 Outbox 이벤트는 같은 DB transaction으로 저장됩니다.

```text
Strategy Worker → strategy_signal + message_outbox
                → Messaging → Trading Queue → Trading Worker
```

Trading이 주문 예산 상태를 변경하면 `AllocationChanged` 이벤트를 Strategy Queue로 보냅니다. Strategy Worker가 이를 소비해 자신의 전략 예산 상태를 반영합니다. Redis는 사용하지 않습니다.
