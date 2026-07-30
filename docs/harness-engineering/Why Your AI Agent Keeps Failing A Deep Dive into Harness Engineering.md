# Why Your AI Agent Keeps Failing: A Deep Dive into Harness Engineering

구분: study
상태: 완료
기술 스택: harness engineering
원문: https://levelup.gitconnected.com/why-your-ai-agent-keeps-failing-a-deep-dive-into-harness-engineering-f579e7609e48
일정: 2026년 4월 2일
등록일: 2026년 4월 2일
프로젝트: Tech (https://www.notion.so/Tech-17909f96fe52804aae0dcf8c7256634e?pvs=21)

![](https://miro.medium.com/v2/resize:fit:700/0*TQmG4VRyWn597lqk.png)

2026년 2월, OpenAI는 엔지니어링 팀이 Codex를 사용하여 5개월 동안 1,500건의 풀 리퀘스트를 통해 코드의 100%를 직접 작성한 과정을 설명하는 블로그 게시물을 발표했습니다. 그 게시물에서 특히 인상 깊었던 구절이 있습니다.

> *엔지니어링 팀의 주요 임무는 에이전트가 유용한 작업을 수행할 수 있도록 지원하는 것이었습니다.*
> 

거의 같은 시기에 LangChain 엔지니어들은 동일한 모델(`gpt-5.2-codex`)을 사용하되, 다른 시스템을 적용한 통제 실험을 진행했습니다. Terminal Bench 2.0 점수가 **52.8%에서 66.5%로** 크게 향상되어 순위가 30위에서 5위로 급상승했습니다.

이 13.7% 포인트의 향상은 모델이 아닌 하네스(Harness)의 개선 덕분입니다.

에이전트는 **Model + Harness**로 구성됩니다. 모델은 성능의 상한선을 설정하고, 하네스는 그 상한선에 얼마나 근접하는지를 결정합니다.

이 글은 하네스 엔지니어링이 *무엇인지*에 대한 것이 아니라, 에이전트 시스템이 특정하고 예측 가능한 방식으로 실패하는 이유와 각 하네스 구성 요소가 이러한 실패에 대응하도록 설계된 방식에 대한 것입니다.

### **The Four Structural Failure Modes**

이것들은 버그가 아닙니다. LLM의 구조적 특성입니다.

**실패 1: 세션 간 상태 유지 실패** LLM에는 영구 메모리가 없습니다. 각 세션은 깨끗한 컨텍스트 창에서 시작합니다. 복잡한 프로젝트에서 다음 세션은 이전 세션에서 무엇을 했는지, 어디까지 진행했는지, 어떤 문제가 발생했는지 알 수 없습니다. 에이전트는 처음부터 다시 시작하거나 이미 완료된 작업을 반복해야 합니다.

**실패 2: 일회성 목표 달성 시도** 에이전트는 전체 목표를 한 번에 완료하려고 하는 경향이 있습니다. 복잡한 프로젝트의 경우, 컨텍스트 창이 작업 도중에 소진되어 코드베이스가 예측할 수 없는 미완성 상태로 남게 됩니다. 다음 세션은 엉망인 상태를 물려받게 됩니다.

**실패 3: 조기 완료** 에이전트는 작업이 완료되지 않았는데도 완료되었다고 주장합니다. 이는 기만 행위가 아니라 신뢰할 수 없는 자체 평가 메커니즘 때문입니다. 에이전트는 코드가 작성된 것을 보고 기능이 제대로 작동한다고 결론짓습니다. 이 두 가지는 서로 다른 문제입니다.

**실패 4: 악순환.** 에이전트가 어려운 문제에 부딪히면 약간씩 변형하여 동일한 접근 방식을 반복합니다. 난이도가 높은 상황에서 LLM 추론은 재평가를 위해 되돌아가기보다는 유사한 해결 공간 내에 머무르는 경향이 있습니다. 동일한 시도를 열 번 반복해도 실패하는 것이 일반적인 패턴입니다.

각 Harness 구성 요소는 시스템 수준에서 이러한 실패 중 하나 이상을 해결합니다.

### **Component 1: Readable Environment**

**모든 상태는 외부화**되어야 합니다. LLM은 상태를 저장하지 않으므로 환경이 이를 관리해야 합니다. OpenAI 팀은 처음에 모든 것을 하나의 거대한 `AGENTS.md` 파일에 담았는데, 곧바로 세 가지 문제에 직면했습니다.

1. **컨텍스트 오염**: 파일 크기가 커질수록 특정 작업에 대한 신호 대 잡음비가 낮아집니다.
2. **정보 노후화 속도**: 큰 파일은 유지 관리 속도보다 훨씬 빠르게 권위적이지만 잘못된 정보가 되어버립니다.
3. **점진적 정보 공개 부재**: 간단한 작업을 계획하는 에이전트는 전체 시스템 사양이 필요하지 않지만, 하나의 거대한 파일은 에이전트가 모든 정보를 처리하도록 강요합니다.

해결책은 정보 축적이 아니라 **정보 아키텍처**에 있습니다. `AGENTS.md` 파일은 하위 문서를 가리키는 목차 역할을 하게 됩니다.

```
AGENTS.md              ← lightweight entry point, rarely changes
├── product-specs/     ← user stories + acceptance criteria (split by feature)
├── design-docs/       ← architecture decisions + ADRs
├── exec-plans/        ← current execution plan, updates frequently
├── db-schema/         ← database schema, auto-generated preferred
└── security/          ← security rules, manually maintained
```

진입점은 안정적으로 유지됩니다. `AGENTS.md` 파일 자체는 거의 변경되지 않으므로, 각 세션은 전체 문서 트리를 로드하지 않고도 항상 현재 하위 문서를 찾을 수 있습니다. 각 하위 문서는 단일 책임, 즉 파일당 하나의 기능만 수행하며 필요에 따라 로드됩니다. LangChain은 이를 `LocalContextMiddleware`로 구현하여 세션 시작 시 디렉터리 구조를 스캔하고 현재 작업과 관련된 컨텍스트만 주입합니다.

AgentsMesh의 52일간의 실천은 이러한 원리를 논리적으로 입증했습니다. **저장소 자체가 가장 중요한 컨텍스트이며, 별도의 RAG 시스템은 필요하지 않습니다.** 단, 문서가 장식적인 것이 아니라 실제로 유지 관리되어야 한다는 전제 조건이 있습니다.

![Two-panel comparison. Left panel with red border: monolithic AGENTS.md (2,400 lines) with mixed content blocks labeled schema, specs, instructions, history, rules — captioned "Context Pollution · Stale Fast · No Progressive Disclosure". Right panel with green border: lightweight AGENTS.md as TOC pointing to five sub-directories (product-specs, design-docs, exec-plans, db-schema, security) — captioned "Stable Entry · Progressive Disclosure · Load On Demand, Terminal Bench 52.8%→66.5%"](https://miro.medium.com/v2/resize:fit:700/0*Z2TWUU82qQtd0-G0.png)

### **Component 2: Task State Machine**

상태 손실, 일회성 욕심(one-shot greed), 조기 완료 — 세 가지 실패가 동시에 발생합니다. OpenAI의 해결책은 작업 관리를 JSON 상태 머신으로 외부화하는 것입니다.

```json
{
  "id": "auth-001",
  "title": "Email login",
  "spec": "Email + password login. Success returns JWT, failure returns 401.",
  "acceptance_criteria": [
    "POST /auth/login accepts email and password",
    "Wrong password returns { error: 'invalid_credentials' }",
    "Token expires in 24 hours, stored as httpOnly cookie."
  ],
  "status": "fail"
}
```

`status`의 기본값은 `pending`이 아닌 `fail`입니다. 이는 의도적인 선택입니다. `pending`은 중립적인 상태, 즉 "아직 완료되지 않음"을 의미합니다. `fail`은 부정적인 상태, 즉 "아직 통과하지 못함"을 의미합니다. 이러한 차이는 인지 수준에서 중요합니다. 에이전트는 작업을 *완료*하는 것이 아니라 *작업 통과를 증명*하는 것입니다. OpenAI는 전체 프로젝트를 200개 이상의 작업으로 나누었고, 모든 작업은 기본적으로 실패로 설정되어 있습니다. 에이전트의 역할은 이러한 작업을 `pass`로 만드는 것입니다.

`acceptance_criteria` 필드는 기계가 읽을 수 있는 계약서이지, 사람이 작성한 문서가 아닙니다. 모든 기준은 프로그램적으로 검증 가능해야 합니다. 테스트로 작성할 수 있다면 테스트로 실행되어야 합니다. 이것이 Harness 내에서 최소한의 필수 Spec 단위입니다.

그리고 기능 목록(Feature List)과 `git log`를 함께 사용하면 현재 상태 스냅샷을 얻을 수 있습니다. 새로운 코딩 에이전트 세션은 이전 에이전트가 암묵적으로 남긴 정보에 의존하지 않고 30초 이내에 프로젝트 상태를 재구성하기 위해 두 파일을 모두 읽습니다. 이것이 상태 손실 악순환을 끊는 핵심입니다.

여기서 중요한 것은 두 계층으로 나뉜 에이전트 구조입니다.

- **초기화 에이전트**: 비즈니스 코드를 작성하지 않습니다. 상속 가능한 환경(기능 목록 JSON(Feature List), `init.sh`(개발 서버 시작), `PROGRESS.txt`(진행 상황 요약), 초기 `git commit`)을 구축합니다.
- **코딩 에이전트**: 각 세션은 상태를 읽고, 가장 우선순위가 높은 `fail` 작업을 선택한 후, 코드를 구현하고, 검증하고, `pass`로 표시한 다음, 커밋하고, `PROGRESS.txt`를 업데이트합니다. 세션은 반드시 깨끗한 상태로 종료되어야 합니다. 이는 권장 사항이 아닌 필수 조건입니다.

![Two-tier flowchart. Top tier: Initializer Agent (runs once) outputs four artifacts — Feature List JSON (200+ tasks, all status:fail), init.sh, PROGRESS.txt, and initial git commit — labeled "Builds inheritable environment". Bottom tier inside blue dashed box labeled "Each session: clean context window": six-step cycle — Read State (git log = session state) → Select Task (highest-priority status:fail) → Implement → Verify → Pass? Yes: update to status:pass and commit, then loop back; No: return to Implement](https://miro.medium.com/v2/resize:fit:700/0*zJKS1QXWdidB1UUP.png)

### **Component 3: Verification Loop**

조기 완료 편향은 구조적인 문제이지, 엔지니어링상의 문제가 아닙니다. 에이전트는 코드를 작성한 후, 방금 코드를 작성한 동일한 컨텍스트 창 내에서 자체 평가를 수행합니다. 이 컨텍스트에는 "코드 작성 완료" 신호가 가득합니다. 따라서 평가가 시작되기도 전에 "작업 완료"에 대한 사전 확률이 이미 왜곡되어 있는 것입니다.

LangChain의 해결책은 `PreCompletionChecklistMiddleware`입니다.

```python
class PreCompletionChecklistMiddleware(AgentMiddleware):
    def before_complete(self, state: AgentState) -> AgentState:
        if not state.get("verification_done"):
            state.inject(SystemMessage(
                "Before marking complete, run the full verification checklist: "
                "1) All acceptance_criteria tests pass "
                "2) No regressions in existing tests "
                "3) End-to-end flow verified"
            ))
            state.set("verification_done", False)
        return state
```

이는 LLM의 알려진 동작을 악용한 것입니다. **즉, 에이전트에게 작업이 프로그래밍 방식 테스트로 평가될 것이라고 명시적으로 알리면 자체 검증 동작이 크게 변경됩니다.** 시스템 메시지가 기준점이 됩니다. 미들웨어는 종료 전에 검증 흐름을 강제합니다.

OpenAI는 다른 접근 방식을 취했습니다. Chrome DevTools 프로토콜을 에이전트 런타임에 직접 통합한 것입니다.

```python
# Agent verification workflow
agent.reproduce_bug(dom_snapshot=True, screenshot=True)
agent.implement_fix()
agent.validate_fix(record_video=True)  # record "after" video
agent.submit_pr(evidence=[before_video, after_video])
```

PR에는 비디오 증거가 포함됩니다. 검토자는 환경을 재구축할 필요가 없습니다. **검증 증거는 텍스트 설명이 아닌 재생 가능한 비디오입니다.** 비디오는 거짓말을 하지 않습니다.

AgentsMesh는 4단계 피드백 루프를 구현했습니다.

```
Compile → Unit tests (700+) → E2E → CI
  ↓ hot reload  ↓ real-time    ↓ full flow  ↓ multi-platform
```

모든 오류는 에이전트에 즉시 피드백됩니다. 강력한 타입 시스템(Go 컴파일러, TypeScript, Protobuf)은 E2E(엔드 투 엔드) 테스트에 도달하기 전에 컴파일 타임에 많은 오류를 잡아냅니다.

한 가지 사례를 들자면, LangChain은 추론 예산을 계획 단계에 최대, 구현 단계에 중간, 검증 단계에 다시 최대로 할당하는 "추론 샌드위치" 방식을 테스트했습니다. 결과는 **63.6% 대 53.9%**였습니다. 검증 단계에서는 추론의 질이 계획만큼 중요합니다. 코드가 작성되었다고 해서 추론 과정을 생략해서는 안 됩니다.

### **Component 4: Architecture Enforcement**

AgentsMesh 개발자의 요약: **에이전트는 코드베이스의 모든 패턴(나쁜 패턴 포함)을 복사합니다.** 이는 버그가 아니라 LLM의 핵심 메커니즘입니다. 패턴 매칭 및 복제인 셈이죠. 기술 부채가 있는 코드베이스에서는 에이전트가 생성하는 코드의 속도만큼 부채가 확산됩니다.

해결책은 **아키텍처 제약 조건을 문서가 아닌 툴에 인코딩하는 것**입니다.

OpenAI의 구현 방식: 도메인 기반 저장소 구조, 단방향 종속성 흐름, 순환 종속성 방지, 사용자 지정 린터 및 모든 `git pre-commit`에 대한 구조적 테스트를 통해 강제 적용.

```bash
# .git/hooks/pre-commit
#!/bin/sh
# Check dependency direction
npx check-deps --config .dep-rules.json || exit 1
# Check naming conventions
npx lint-names --strict || exit 1
# Check architecture boundaries
go test ./cmd/check-arch/... || exit 1
```

위반 사항은 경고를 발생시키지 않고 커밋을 차단합니다.

**강력한 타입 시스템은 아키텍처를 무료로 강제할 수 있는 방법입니다.** Go 컴파일러, TypeScript의 타입 체커, Protobuf 스키마 정의와 같이 컴파일 시점에 포착되는 오류는 E2E 테스트까지 도달하지 않습니다. AgentsMesh는 검증 루프 비용을 줄이기 위해 가능한 한 많은 제약 조건을 컴파일 시점에 적용했습니다.

**아키텍처 규율은 첫날부터 시작해야 하는 것이지, 100일 후에 하는 것이 아닙니다.** 기존 팀들은 엔지니어의 직관, 즉 "뭔가 잘못됐다"는 느낌 때문에 규모가 커질 때까지 아키텍처 경계를 설정하는 것을 미뤄왔습니다. 하지만 에이전트는 그런 직관이 없습니다. 에이전트는 도구에 인코딩된 규칙만 따릅니다. 코드베이스에 상당한 기술적 부채가 쌓인 후에 제약 조건을 추가하는 것은 처음부터 시작하는 것보다 훨씬 더 많은 비용이 듭니다.

### **Component 5: Loop Detection**

에이전트가 어려운 문제에 부딪히면, 점점 더 많은 노력을 들여 유사한 접근 방식을 반복합니다. 이는 무작위 보행이 아니라 방향성을 가진 탐색입니다. 각 시도는 이전 시도보다 "더 어렵지만", 방향은 잘못되었습니다. 동일한 시도가 10번 반복되어 실패하는 것이 일반적인 패턴이며, 토큰 소모는 선형적이고, 문제는 해결되지 않은 채로 남습니다.

LangChain’s `LoopDetectionMiddleware`:

```python
class LoopDetectionMiddleware(AgentMiddleware):
    def __init__(self, threshold: int = 5):
        self.file_edit_counts: Dict[str, int] = {}
        self.threshold = threshold

    def after_edit(self, file: str) -> Optional[Intervention]:
        self.file_edit_counts[file] = self.file_edit_counts.get(file, 0) + 1
        if self.file_edit_counts[file] > self.threshold:
            return Intervention(
                f"You've edited {file} {self.file_edit_counts[file]} times. "
                "Consider an entirely different approach or ask for help."
            )
        return None
```

파일별 편집 횟수를 추적합니다. 임계값을 초과하면 개입합니다. 핵심은 *개입*입니다. 에이전트가 작업을 완료한 후 알리는 것이 아니라, 루프가 진행되는 동안 추론 관성을 깨뜨리는 것입니다.

**랄프 루프 패턴**: 여러 세션에 걸쳐 장시간 실행되는 작업의 경우, LangChain은 각 세션 시작 시 깨끗한 컨텍스트 창에 목표 프롬프트를 다시 삽입합니다. 이를 통해 여러 세션에 걸쳐 작업 목표가 흐려지는 것을 방지합니다. 구현은 간단합니다. 세션 시작 시 기능 목록에서 우선순위가 가장 높은 미완료 작업을 다시 삽입하면 됩니다.

**인지 대역폭 한계**: AgentsMesh는 인간의 의사 결정 한계를 **하루 5만 줄**로 설정합니다. 그 이상에서는 수동 검토가 의미를 잃게 됩니다. 이는 기술 부족 때문이 아니라 인지 대역폭 고갈 때문입니다. 이 한계를 넘어서면 의사 결정을 상위 수준의 조정 에이전트에 위임해야 하며, 불가능한 검토 작업을 인간에게 강요해서는 안 됩니다.

### **How the Five Components Work Together**

검증 루프를 추가한다고 해서 그것이 태스크 상태 머신의 `acceptance_criteria` 필드에 의존한다는 것을 바로 알 수는 없습니다. 다섯 가지 구성 요소는 하나의 시스템을 이루며, 각 구성 요소 간의 결합은 매우 구체적입니다.

**읽기 쉬운 환경**은 모든 것의 기반입니다. 저장소에 저장된 기능 목록, 아키텍처 규칙, 승인 기준은 문서 구조가 제대로 갖춰져 있고 유지 관리될 때에만 에이전트가 유용하게 사용할 수 있습니다.

**태스크 상태 머신**의 `acceptance_criteria` 필드는 **검증 루프**의 입력값입니다. `PreCompletionChecklistMiddleware`는 이러한 기준을 검사합니다. 두 구성 요소는 이 단일 필드를 통해 연결됩니다.

**아키텍처 강제**의 커밋 전 후크는 **검증 루프**의 일부입니다. 각 커밋은 아키텍처 검사를 트리거하며, 이는 4계층 피드백 주기의 한 단계입니다.

**루프 감지**는 **태스크 상태 머신**의 처리량을 보호합니다. 이 기능이 없으면, 하나의 정체된 작업에서 토큰이 소모되는 것만으로도 전체 기능 목록이 중단될 수 있습니다.

이 다섯 가지 구성 요소는 다음과 같은 질문에 대한 답을 제시합니다. **상태 비저장, 탐욕적, 자체 평가 기능 부족, 무한 루프에 취약한 LLM을 복잡하고 장기 실행되는 프로젝트에서 안정적으로 작동시키려면 어떻게 해야 할까요?**

![Harness five-component dependency map. Bottom foundation layer: dark wide bar "Readable Environment" (AGENTS.md TOC, product-specs, design-docs, exec-plans). Center: blue "Task State Machine" (Feature List JSON, status fail/pass, acceptance_criteria). Left: green "Verification Loop" (PreCompletionChecklist, Chrome DevTools, 4-layer feedback) coupled to Task State Machine via "acceptance_criteria field" arrow. Right: red "Loop Detection" (LoopDetectionMiddleware, threshold=5, Ralph Loop) connected via "monitors edit count". Top: purple "Architecture Enforcement" (custom linter, structural tests, dependency rules) connected to Verification Loop via "pre-commit hook", labeled "pre-commit = feedback loop step"](https://miro.medium.com/v2/resize:fit:700/0*qe9PolSq7d413uZb.png)

### **Open Source References**

**LangChain DeepAgents** ([github.com/langchain-ai/deepagents](https://github.com/langchain-ai/deepagents)) 위에 언급된 모든 미들웨어는 오픈 소스 구현체를 제공합니다. `write_todos`, `LocalContextMiddleware`, `PreCompletionChecklistMiddleware`, `LoopDetectionMiddleware`는 직접 사용하거나 참조용으로 활용할 수 있습니다. 가상 파일 시스템 백엔드는 플러그인 방식으로 확장 가능합니다.

**AgentsMesh** ([V2EX 스레드](https://v2ex.com/t/1196036)) 52일 동안 96만 줄의 처리량을 달성했으며, 현재 35만 줄의 코드가 실제 운영 환경에서 실행되고 있습니다. DDD 기반의 계층형 아키텍처(도메인/서비스/핸들러)는 아키텍처 경계가 에이전트가 코드를 추가해야 하는 위치를 명확하게 보여줍니다. 4계층 피드백 루프의 완벽한 엔지니어링 구현체입니다.

**DeerFlow**(ByteDance 오픈 소스) `deerflow-harness` 패키지는 에이전트 엔지니어링 계층을 비즈니스 로직에서 분리합니다. 이는 "플러그형 계층으로서의 하네스"를 의미합니다.

Community list: [github.com/walkinglabs/awesome-harness-engineering](https://github.com/walkinglabs/awesome-harness-engineering)

### **Summary**

모델 자체가 병목 현상은 아닙니다. LangChain은 동일한 모델을 사용하면서도 다른 Harness를 적용하여 13.7%포인트의 성능 향상을 달성함으로써 이를 입증했습니다.

네 가지 구조적 실패 모드(상태 손실, 일회성 탐욕, 조기 완료, 무한 루프)는 LLM 아키텍처에서 비롯됩니다. 더 나은 프롬프트로는 이러한 문제를 해결할 수 없습니다.

Harness의 다섯 가지 구성 요소가 이러한 문제를 해결합니다. 상태를 단일 파일이 아닌 정보 아키텍처 형태로 외부화하고, 기본적으로 `status: fail`을 사용하며, 기계 판독 가능한 `acceptance_criteria`를 제공합니다. 또한 실제 증거(미들웨어, 비디오, 추론 샌드위치)를 기반으로 검증 루프를 구축하고, 코드베이스에 부채가 쌓이기 전에 아키텍처 제약 조건을 툴링에 반영하며, 사후 분석이 아닌 실시간으로 루프를 중단시킵니다.

이것들은 단순한 체크리스트가 아니라 시스템입니다. 핵심은 구성 요소 간의 결합 관계입니다.