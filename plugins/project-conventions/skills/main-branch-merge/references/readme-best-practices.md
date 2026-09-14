# README.md 작성 베스트 프랙티스

이 문서는 main-branch-merge 스킬이 README.md를 생성/업데이트할 때 참조하는 가이드라인이다.

---

## 핵심 원칙

README.md의 목적은 **프로젝트에 처음 접하는 개발자가 5분 내에 프로젝트를 이해하고 로컬에서 실행할 수 있게 하는 것**이다. 이 원칙에 부합하지 않는 내용은 제외하거나 별도 문서로 분리한다.

---

## 필수 섹션 (순서대로)

### 1. 프로젝트 제목 + 배지

```markdown
# 프로젝트명

[![Platform](https://img.shields.io/badge/platform-iOS%20%7C%20Android-blue)]()
[![Expo SDK](https://img.shields.io/badge/Expo%20SDK-55-000020)]()
[![TypeScript](https://img.shields.io/badge/TypeScript-strict-3178C6)]()
[![License](https://img.shields.io/badge/license-MIT-green)]()
```

- 배지는 한 줄에 나열 (최대 5개)
- 의미 있는 배지만 사용: Platform, SDK 버전, 언어, 라이선스, CI 상태
- 빈 URL `()` 대신 실제 링크가 있으면 연결

### 2. 한줄 소개

```markdown
> 인터넷 연결 없이 기기 내 AI만으로 종이책을 목차별로 디지털 요약·저장하는 모바일 앱
```

- 프로젝트가 **무엇인지** + **핵심 차별점**을 1~2문장으로 전달
- 기술 용어보다 사용자 가치 중심으로 작성

### 3. 주요 기능 (Features)

```markdown
## 주요 기능

- 📷 **표지/목차 자동 인식** — 카메라로 촬영하면 OCR로 목차 구조 추출
- 🤖 **온디바이스 AI 요약** — Edge SLM으로 챕터별 요약 생성 (인터넷 불필요)
- 🔍 **전문 검색** — FTS5 기반 빠른 전체 텍스트 검색
- 🔒 **프라이버시 보호** — 모든 데이터가 기기 안에만 저장
```

- 각 항목은 아이콘 + **볼드 제목** + 한줄 설명
- 사용자가 체감할 수 있는 기능 위주 (내부 구현 X)
- 4~8개 항목이 적당

### 4. 스크린샷 / 데모

```markdown
## 스크린샷

|                라이브러리                |               목차 스캔               |                 AI 요약                  |
| :--------------------------------------: | :-----------------------------------: | :--------------------------------------: |
| ![Library](docs/screenshots/library.png) | ![ToC](docs/screenshots/toc-scan.png) | ![Summary](docs/screenshots/summary.png) |
```

- UI 프로젝트에서 스크린샷은 **필수** (없으면 `<!-- TODO: 스크린샷 추가 -->` placeholder)
- 가로 3열 테이블 또는 `<img>` 태그로 크기 제어
- 스크린샷 파일은 `docs/screenshots/` 디렉토리에 저장

### 5. 기술 스택

```markdown
## 기술 스택

| 분류       | 기술                                |
| ---------- | ----------------------------------- |
| Framework  | React Native Expo (SDK 55)          |
| Language   | TypeScript (strict mode)            |
| Navigation | expo-router v3                      |
| State      | Zustand + MMKV                      |
| Database   | expo-sqlite + FTS5                  |
| AI/OCR     | ML Kit OCR, MediaPipe LLM Inference |
| Test       | Jest, Detox                         |
```

- 실제 `package.json`의 dependencies와 일치해야 함
- 주요 기술만 포함 (유틸리티 라이브러리는 생략)

### 6. 시작하기 (Getting Started)

이 섹션이 README의 핵심이다. 복사-붙여넣기로 실행 가능해야 한다.

#### 6-1. Prerequisites

```markdown
### Prerequisites

- Node.js >= 18
- npm >= 9 (또는 yarn)
- Expo CLI: `npm install -g expo-cli`
- iOS: Xcode 15+ (시뮬레이터용)
- Android: Android Studio + SDK 34 (에뮬레이터용)
- EAS CLI (빌드용): `npm install -g eas-cli`
```

- 정확한 최소 버전 명시
- OS별 차이가 있으면 분리

#### 6-2. Installation

```markdown
### 설치

# 저장소 클론

git clone https://github.com/{owner}/{repo}.git
cd {repo}

# 의존성 설치

npm install

# iOS 네이티브 의존성 (macOS)

npx pod-install

# 개발 서버 시작

npx expo start
```

- 각 명령어에 주석으로 목적 설명
- Expo 프로젝트 특화: `expo-dev-client` 필요 여부, prebuild 설명
- 네이티브 모듈 사용 시 `npx expo prebuild` 또는 `eas build` 안내

#### 6-3. Environment Configuration

```markdown
### 환경 설정

이 프로젝트는 외부 API를 사용하지 않으므로 별도 환경변수가 필요하지 않습니다.

# (API 키가 필요한 프로젝트의 경우)

# .env.example을 복사하여 .env를 생성하세요:

# cp .env.example .env
```

- `.env.example` 파일이 있으면 각 변수 설명
- 없으면 "환경변수 불필요" 명시

### 7. 프로젝트 구조

```markdown
## 프로젝트 구조

src/
├── app/ # 파일 기반 라우팅 (expo-router)
│ ├── (tabs)/ # 탭 네비게이션
│ ├── book/ # 도서 상세
│ └── camera.tsx # 카메라 촬영
├── components/ # 공통 UI 컴포넌트
├── stores/ # Zustand 상태 관리
├── services/ # 비즈니스 로직
├── hooks/ # 커스텀 훅
├── constants/ # 상수 (색상, 스타일 토큰)
├── types/ # TypeScript 타입 정의
└── utils/ # 유틸리티 함수
```

- 실제 디렉토리 구조와 일치해야 함 (코드 분석 결과 반영)
- 주요 디렉토리만 2~3 depth까지 표시
- 각 디렉토리 옆에 한줄 설명

### 8. 사용 가능한 스크립트

```markdown
## 스크립트

| 명령어              | 설명                  |
| ------------------- | --------------------- |
| `npm start`         | Expo 개발 서버 시작   |
| `npm test`          | Jest 단위 테스트 실행 |
| `npm run lint`      | ESLint 검사           |
| `npm run typecheck` | TypeScript 타입 체크  |
| `npm run format`    | Prettier 포맷팅       |
```

- `package.json`의 scripts 섹션과 일치
- 자주 사용하는 것 위주

### 9. 아키텍처 (선택)

프로젝트 아키텍처가 독특하거나 복잡한 경우에만 포함.

```markdown
## 아키텍처

Presentation → Business Logic → AI Engine → Data Layer

모든 AI 추론은 온디바이스로 수행되며, 외부 API 호출이 없습니다.
```

- 4계층 이상이면 다이어그램 또는 Mermaid 사용
- 핵심 아키텍처 결정만 포함

### 10. 기여 가이드 (Contributing)

```markdown
## 기여 방법

1. Fork
2. Feature 브랜치 생성 (`git checkout -b feature/amazing-feature`)
3. 커밋 (`git commit -m 'feat: add amazing feature'`)
4. Push (`git push origin feature/amazing-feature`)
5. Pull Request 생성

### 커밋 컨벤션

Conventional Commits 형식을 따릅니다: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
```

### 11. 라이선스

```markdown
## 라이선스

이 프로젝트는 MIT 라이선스를 따릅니다. 자세한 내용은 [LICENSE](LICENSE) 파일을 참조하세요.
```

- LICENSE 파일이 존재하면 해당 라이선스 표시
- 없으면 이 섹션 생략 또는 `<!-- TODO: 라이선스 추가 -->` placeholder

---

## React Native / Expo 프로젝트 특화 가이드

### Development Build vs Expo Go

```markdown
### 개발 빌드

이 프로젝트는 네이티브 모듈을 사용하므로 Expo Go 대신 Development Build가 필요합니다.

# 개발 빌드 생성

eas build --profile development --platform ios
eas build --profile development --platform android

# 또는 로컬 빌드

npx expo prebuild
npx expo run:ios
npx expo run:android
```

- 네이티브 모듈 사용 시 반드시 Development Build 안내
- Expo Go로 실행 가능하면 그것도 명시

### EAS Build

```markdown
### 프로덕션 빌드

# EAS 로그인

eas login

# 프로덕션 빌드

eas build --platform all

# 앱 제출 (App Store / Play Store)

eas submit --platform all
```

### OTA 업데이트

`expo-updates` 사용 시:

```markdown
### OTA 업데이트

eas update --branch production --message "v1.2.0 핫픽스"
```

---

## 포맷팅 규칙

1. **코드 블록에 언어 명시**: ` ```bash `, ` ```typescript `, ` ```sql `
2. **링크는 상대 경로 우선**: `[문서](docs/guide.md)` > 절대 URL
3. **이미지 크기 제어**: `<img src="..." width="300">` 또는 테이블 레이아웃
4. **줄 바꿈**: 섹션 사이 빈 줄 1개, 코드 블록 전후 빈 줄 1개
5. **목록 들여쓰기**: 2칸 또는 4칸 일관 유지

---

## 안티패턴 — 하지 말아야 할 것

- **빈 섹션**: `## 기여 방법\n\nTBD` → 섹션 자체를 제거하거나 placeholder를 넣되, 빈 상태로 두지 않는다
- **오래된 설치 명령어**: 실제 `package.json`과 다른 명령어
- **스크린샷 없는 UI 프로젝트**: 최소 1개의 스크린샷이 필요
- **과도한 배지**: 10개 이상의 배지는 시각적 노이즈
- **복사 불가능한 코드**: 프롬프트 기호(`$`, `>`)가 코드 블록 안에 포함
- **하드코딩된 버전**: "Node.js 16" 같은 오래될 정보 → 최소 버전 표기 권장
- **README에 모든 API 문서**: API 레퍼런스는 별도 docs/로 분리

---

## 증분 업데이트 규칙

기존 README.md가 있을 때:

1. 기존 섹션 **순서와 구조를 유지**
2. 내용만 최신 코드에 맞게 업데이트
3. 새로운 섹션이 필요하면 적절한 위치에 삽입
4. 사용자가 커스터마이징한 섹션(예: 프로젝트 소개 문구)은 수정하지 않되, 기술적 정보(버전, 스크립트 등)는 업데이트
5. 기존에 없던 필수 섹션은 추가
