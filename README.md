# SignalTrade Strategy

시세 수집, 전략 설정·평가, 매수·매도 신호 생성을 맡는 서비스입니다.

```text
src/signaltrade_strategy/  API·Worker·시세 처리
tests/                     전략 계산과 API 테스트
```

Frontend는 전략 목록과 구독을 HTTP로 조회·변경합니다. Worker가 확정한 신호는 Outbox에 기록되고 Messaging이 Queue로 발행하면 Trading이 주문 처리합니다.
