# Progress — release-impl v0.8.0

> Last Updated: 2026-03-25 19:30
> Total Tasks: 5 | Pass: 4 | Fail: 0 | Blocked: 1

## 현재 상태

- 단계: TASK-005 blocked로 중단, 사용자 개입 대기
- 다음 작업: 해당 task는 v0.9.0에서 이어 진행하기로 결정
- 차단 사항: 외부 API(Stripe) 서명 검증 스펙 변경 확인 필요

## 세션 로그

- [2026-03-20] TASK-001 결제 입력 검증 개선 완료 (usePaymentForm validate 분리)
- [2026-03-21] TASK-002 일본어(ja) i18n 번역 리소스 추가 완료
- [2026-03-23] TASK-003 프로필 화면 캐시 개선 완료
- [2026-03-24] TASK-004 결제 에러 메시지 포맷 통일 완료
- [2026-03-25] TASK-005 결제 웹훅 재시도 큐 — Stripe 서명 로테이션 이슈로 blocked

## 발견된 이슈

- **[결제 · TASK-001 구현 중 관찰]** usePaymentForm의 validate 함수에서 빈 입력이 들어왔을 때 타입이 `undefined | string`으로 추론되어 조용히 통과하던 버그가 있었음. v0.9.0에서 같은 훅 수정 시 타입 가드 유지 확인 필요.
- **[결제 웹훅 · TASK-005 blocked 원인]** Stripe 서명 검증에서 `stripe-signature` 헤더 로테이션 이후 기존 구현이 401을 반환. 재시도 로직에 지수 backoff 없이 즉시 재요청하여 rate limit에 걸림. v0.9.0에서 재개 시 backoff부터 설계 필요.
- **[BG 타이머]** 결제 폴링에 `setTimeout`을 사용했는데 iOS 백그라운드에서 멈춤. `BackgroundTimer` 라이브러리로 교체 필요 — 같은 파일을 건드릴 때 주의.

## 아키텍처 결정

- 결제 관련 핸들러는 `src/lib/payment.ts`에 집약한다.
- 웹훅 처리는 별도 모듈 `src/lib/webhookQueue.ts`로 분리 (v0.8.0에서 파일은 만들었지만 내부는 blocked).
