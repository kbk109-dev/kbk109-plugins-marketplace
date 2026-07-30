# CLAUDE.md — PayFlow (eval fixture)

이 저장소는 release-impl 스킬의 eval을 위한 가상 프로젝트다. 실제 빌드/테스트는 수행되지 않으며, 스킬이 CLAUDE.md 계약을 올바르게 읽고 반영하는지를 평가하기 위해 필요한 최소 정보만 포함한다.

## 기술 스택

- 언어: TypeScript (React Native + Expo 관리형)
- 패키지 매니저: npm

## 명령

- 테스트: `npm test`
- 타입 검사: `npx tsc --noEmit`
- 린트: `npx eslint src/`

## 디렉토리 구조

- 소스: `src/`
- 테스트: `src/**/__tests__/`
- Screens: `src/screens/`
- Hooks: `src/hooks/`
- 공통 유틸: `src/lib/`

## 네이밍 컨벤션

- 변수/함수: `camelCase`
- 타입/컴포넌트: `PascalCase`
- 훅: `use{Feature}` 형식
- 테스트 파일: `*.test.ts` 또는 `*.test.tsx`

## 임포트 경로

- path alias `@/` → `src/`
- 상대 경로는 같은 디렉토리 내에서만 사용

## 커밋 컨벤션

Conventional Commits 사용. 타입: `feat`, `fix`, `chore`, `docs`, `test`, `refactor`. 스코프는 릴리즈 작업에서 `release/v{version}` 사용.
