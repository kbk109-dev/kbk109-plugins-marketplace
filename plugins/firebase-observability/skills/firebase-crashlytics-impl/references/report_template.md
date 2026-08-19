# 구현 리포트 템플릿

`firebase-crashlytics-impl` 스킬 Phase 3.2 에서 구현 리포트를 생성할 때 쓰는 템플릿이다.
아래 블록을 그대로 채워 쓴다.

```markdown
# Firebase Crashlytics 구현 리포트

> Implemented: YYYY-MM-DD HH:mm
> Based on: CRASHLYTICS_PLAN.md (Last Updated: <plan의 타임스탬프>)
> Harness Dir: docs/harness/firebase/crashlytics/
> Harness: Three-Agent Architecture (Planner -> Generator -> Evaluator)

## 구현 요약

| 항목                          | 수치  |
| ----------------------------- | ----- |
| 총 태스크                     | N개   |
| 통과(pass)                    | N개   |
| 차단(blocked)                 | N개   |
| 생성된 파일                   | N개   |
| 수정된 파일                   | N개   |
| Error Boundary 배치           | N개소 |
| recordError 삽입              | N개소 |
| 커스텀 로그 포인트            | N개소 |
| 커스텀 속성 설정              | N개소 |
| Generator-Evaluator 루프 횟수 | N회   |

## Context7 문서 기준 변경사항

| 항목 | CRASHLYTICS_PLAN.md 기준 | Context7 최신 문서 기준 | 적용된 버전 |
| ---- | ------------------------ | ----------------------- | ----------- |

## 스프린트별 결과

### Sprint 1: SDK 초기화

| Task ID | 제목 | Status | 검증 횟수 |
| ------- | ---- | ------ | --------- |

### Sprint 2: ...

...

## 패키지 설치 결과

| 패키지 | 설치 상태 | 버전 | 비고 |
| ------ | --------- | ---- | ---- |

## 설정 파일 변경

| 파일 | 변경 내용 |
| ---- | --------- |

## 생성된 파일 목록

| 파일 경로 | 설명 |
| --------- | ---- |

## 수정된 파일 목록

| 파일 경로 | 변경 내용 |
| --------- | --------- |

## 구현된 항목 체크리스트

### 글로벌 에러 핸들링

- [x/] 항목

### Error Boundary

- [x/] 항목

### 수동 에러 리포팅 (recordError)

- [x/] 항목

### 커스텀 로그 (Breadcrumb)

- [x/] 항목

### 커스텀 속성

- [x/] 항목

### 사용자 식별

- [x/] 항목

### 동의 관리

- [x/] 항목

## Blocked 태스크 (미완료)

| Task ID | 제목 | 차단 사유 | 권장 조치 |
| ------- | ---- | --------- | --------- |

## 다음 단계

- dev client 재빌드: npx expo run:android (또는 ios)
- crashlytics().crash()로 테스트 크래시 전송하여 대시보드 수신 확인
- 비치명적 에러 recordError 전송 확인
- dSYM / 소스맵 업로드 확인 (스택트레이스 심볼리케이션)
- Firebase Console Crashlytics 대시보드에서 커스텀 키-값 확인
- Blocked 태스크 수동 검토 및 해결

## Changelog

- YYYY-MM-DD: 초기 구현
```
