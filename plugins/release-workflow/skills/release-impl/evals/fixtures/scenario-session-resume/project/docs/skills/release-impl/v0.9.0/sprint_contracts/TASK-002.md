# Sprint Contract — TASK-002

## 예상 수정 파일
- src/lib/webhookQueue.ts (재시도 로직 추가)
- src/lib/__tests__/webhookQueue.test.ts (신규)

## 예상 검증 커맨드
- npm test -- src/lib/__tests__/webhookQueue.test.ts
- npx tsc --noEmit

## 예상 실패 가능점
- v0.8.0의 Stripe 서명 로테이션 이슈가 재발할 수 있음. 계약 착수 전 v0.8.0 PROGRESS.md의 "발견된 이슈" 참조 필요
