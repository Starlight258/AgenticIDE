# Agent 아키텍처 결정 가이드 (Anthropic 기반)

> **목적**: 실제 agent 아키텍처를 결정할 때 (DH case study 포함) 참고할 의사결정 정본. **출처**: Anthropic 공식 엔지니어링 블로그 4편 + Agent Skills 개방 표준. 2024-12 ~ 2025-12. **톤**: practical / explicit / engineering-first / constraint-aware / reversible / honest.

---

## TL;DR (한 줄 요약)

복잡한 AI 프레임워크(LangChain 같은 도구)는 대부분의 경우 **잘못된 출발점**이다. 가장 단순한 설계로 시작하고, 눈으로 확인할 수 있는 이득이 생길 때만 복잡도를 높여라.

"워크플로우"와 "에이전트"는 같은 AI 시스템을 구성하는 양 극단이다.

- **워크플로우(Workflow)**: 코드가 흐름을 정해놓은 것. if문처럼 미리 짜둔 경로대로만 움직인다.
- **에이전트(Agent)**: AI(LLM)가 스스로 판단하며 도구를 호출하면서 루프(반복)를 돌리는 것.

실제 서비스에서 쓰는 시스템 대부분은 **워크플로우라는 뼈대 안에 작은 에이전트 루프 한두 개가 박혀있는 형태**면 충분하다.

컨텍스트(AI가 한 번에 볼 수 있는 텍스트의 범위)는 한정된 자원이고, AI 내부 계산은 입력이 길어질수록 기하급수적(n²)으로 복잡해진다. 그러니 **토큰(AI가 읽고 쓰는 단위)을 적게 쓰는 것 = 정확도를 지키는 것**이다.

멀티 에이전트(여러 AI가 협력하는 구조)는 단순 채팅 대비 **15배 더 비싸지만 90% 더 정확**할 수 있는 특정 상황에서만 쓸 이유가 있다. 즉, 작업의 가치가 높고, 병렬로 처리할 수 있고, 에이전트끼리 실시간으로 서로 의존할 필요가 없을 때만.

---

## 출처 지도

이 문서는 아래 6개 글을 기반으로 만들어졌다. 시간순으로 읽으면 Anthropic이 1년 동안 어느 방향으로 더 집중했는지 보인다. 결론: **단순함을 유지하되, 컨텍스트와 세션 관리에 더 집중**하는 방향이었다.

| 글                                               | 날짜       | 역할                                                                               |
| ------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------- |
| **Building Effective Agents**                    | 2024-12-19 | 뼈대 — 워크플로우/에이전트 구분, 6개 패턴                                          |
| **How we built our multi-agent research system** | 2025-06-13 | 오케스트레이터-워커 실전 경험 + 토큰 비용 분석                                     |
| **Effective context engineering for AI agents**  | 2025-09-29 | 컨텍스트를 "유한한 자원"으로 다루는 방법 — just-in-time / compaction / note-taking |
| **Effective harnesses for long-running agents**  | 2025-11-26 | 여러 세션에 걸쳐 AI가 일관되게 작업하게 하는 구조                                  |
| **Agent Skills (open standard)**                 | 2025-12    | SKILL.md — 동적으로 불러오는 능력(capability) 패키지                               |
| **Claude Agent SDK**                             | 2025+      | 도구 사용(tool-use) 기반 에이전트 루프의 단순한 구현체                             |

---

## 1. 멘탈 모델 — Workflow vs. Agent

워크플로우와 에이전트를 어떻게 구분하는지 한눈에 보자.

|                      | Workflow (워크플로우)               | Agent (에이전트)                        |
| -------------------- | ----------------------------------- | --------------------------------------- |
| 흐름을 누가 결정하나 | 코드가 결정 (미리 짜둔 경로대로)    | LLM(AI)이 스스로 결정 (반복 루프)       |
| 예측 가능성          | 높다 (항상 같은 경로를 탄다)        | 낮다 (AI가 매번 다른 판단을 할 수 있다) |
| 어떤 작업에 맞나     | "A면 B를 해라"처럼 분기가 명확할 때 | 몇 단계가 필요한지 미리 셀 수 없을 때   |
| 비용                 | 낮다                                | 워크플로우 대비 4~15배 비싸다           |
| AI 판단에 대한 신뢰  | 별로 필요 없다                      | AI가 알아서 판단하므로 신뢰가 필요하다  |

> "에이전트는 LLM이 도구를 루프(반복)로 자율적으로 사용하는 것이다." — _Effective context engineering, 2025-09_

**핵심**: 워크플로우냐 에이전트냐는 이분법이 아니다. 두 개를 **시스템 안에 함께 쓰는 것**이 일반적이다. 대부분의 실제 서비스는 워크플로우라는 뼈대 안에 작은 에이전트 루프가 박혀있는 **혼합(hybrid) 형태**다.

---

## 2. 6개 기본 패턴 (Dec 2024)

AI 에이전트 시스템을 설계할 때 쓸 수 있는 대표적인 패턴 6가지다. 이 패턴들은 "규칙"이 아니라 **조립할 수 있는 부품**이다. 조합하고 변형해서 특정 상황에 맞게 써라. 복잡도는 측정 가능한 이득이 있을 때만 추가해라.

### 1. Augmented LLM (강화된 단일 LLM 호출)

- **뭔가요?** 검색(retrieval), 도구(tools), 메모리(memory)를 붙여서 AI를 한 번 호출하는 것.
- **언제 쓰나?** 단일 AI 호출과 추가 정보만으로 충분히 해결될 때.

### 2. Prompt Chaining (프롬프트 연결)

- **뭔가요?** 작업을 N개의 단계로 쪼개고, 각 단계 사이에 검증 과정(gate)을 두는 것. 예를 들어 "번역 → 교정 → 요약" 처럼 순서대로 AI를 여러 번 호출하는 방식.
- **언제 쓰나?** 작업이 명확히 고정된 단계로 나뉘고, 정확도가 높아지는 게 레이턴시(응답 속도) 증가를 감수할 만한 가치가 있을 때.

### 3. Routing (라우팅 — 입력 분류 후 전문 처리)

- **뭔가요?** 들어온 입력을 먼저 분류하고, 각 종류에 맞는 전문 프롬프트나 AI 모델로 분기(나눠 보내는 것)하는 방식. 예: 쉬운 질문은 빠르고 저렴한 Haiku 모델로, 어려운 질문은 더 강력한 Sonnet 모델로.
- **언제 쓰나?** 입력의 종류가 뚜렷이 다르고, 하나의 프롬프트로 모두 처리하면 성능이 떨어질 때.

### 4. Parallelization (병렬화)

- **뭔가요?** 두 가지 방식이 있다.
  - **Sectioning**: 독립적으로 처리할 수 있는 하위 작업들을 동시에 처리.
  - **Voting**: 같은 작업을 N번 돌리고 결과를 합산해서 신뢰도를 높이는 것.
- **언제 쓰나?** 병렬로 처리 가능한 작업이 있고, 여러 관점의 결과를 합치는 것이 신뢰도를 높일 때.

### 5. Orchestrator-Workers (오케스트레이터-워커)

- **뭔가요?** 중앙 AI(오케스트레이터)가 작업을 동적으로 쪼개서 여러 하위 AI(워커)에게 위임하고, 결과를 모아서 합치는 구조.
- **언제 쓰나?** 하위 작업의 수와 형태를 미리 알 수 없을 때. 즉, 작업이 얼마나 복잡해질지 사전에 모를 때.

### 6. Evaluator-Optimizer (평가자-최적화자)

- **뭔가요?** AI 하나가 결과물을 만들고(생성자), 다른 AI가 그걸 평가하고 피드백을 주며(평가자) 반복 개선하는 루프.
- **언제 쓰나?** "좋은 결과"의 기준이 명확하고, 반복 개선이 측정 가능한 가치를 줄 때.

---

## 3. 2025 업데이트 — 멀티 에이전트의 토큰 경제학

_출처: Multi-agent research system, 2025-06_

### 핵심 결론

멀티 에이전트 시스템은 단일 에이전트에 비해 평가에서 **90.2% 더 나은 성능**을 보였다 (Opus 4가 리드하고 Sonnet 4가 서브 에이전트로 구성된 경우).

성능 차이의 **80%는 토큰 사용량으로 설명**된다. 멀티 에이전트는 결국 "더 많은 토큰을 쓸 수 있는 구조"이기 때문에 이긴다. 하지만:

- 멀티 에이전트는 단순 채팅 대비 **15배** 더 많은 토큰을 쓴다.
- 단일 에이전트도 단순 채팅 대비 **4배** 더 많은 토큰을 쓴다.

### 멀티 에이전트가 정당화되는 조건

> "멀티 에이전트 시스템은 많은 병렬화가 필요하고, 정보량이 단일 컨텍스트 창을 초과하며, 수많은 복잡한 도구를 다뤄야 하는 가치 있는 작업에서 뛰어나다." — _Multi-agent post_

다음 조건이 모두 맞을 때만 멀티 에이전트를 쓰는 게 맞다:

- **작업의 가치가 토큰 비용보다 훨씬 높을 때** (리서치, 실사(due diligence), 종합 조사 같은 일).
- **작업이 본질적으로 병렬로 처리 가능할 때** — 서로 같은 정보를 공유할 필요 없이 독립적으로 탐색할 수 있는 경우.
- **에이전트끼리 실시간으로 협의하는 의존도가 낮을 때**.

### 멀티 에이전트가 맞지 않는 곳

> "대부분의 코딩 작업은 리서치보다 진정으로 병렬화할 수 있는 작업이 적고, LLM 에이전트는 아직 실시간으로 다른 에이전트와 조율·위임을 잘 못 한다." — _같은 글_

→ **코딩 도메인에서 멀티 에이전트는 보통 손해**다. 단일 에이전트 + 좋은 도구 + 잘 설계된 컨텍스트가 더 강하다.

### Orchestrator-Worker 실전에서 배운 것들

- **리드(오케스트레이터)가 워커에게 위임할 때 최대한 상세하게 지시해야 한다.** "X를 리서치해줘" 같은 짧은 지시는 중복 작업이나 누락을 부른다. 각 서브 에이전트는 다음을 받아야 한다: _목표 / 출력 형식 / 사용할 도구와 소스 / 작업 범위_.
- **작업의 복잡도에 맞게 노력(에이전트 수)을 조절해야 한다.**
  - 단순 사실 찾기 = 에이전트 1개 + 도구 호출 3~10번
  - 복잡한 비교 분석 = 서브 에이전트 2~4개 + 도구 호출 10~15번
  - 대규모 조사 = 서브 에이전트 10개 이상
- **넓게 시작해서 좁혀나가야 한다 (Wide → Narrow).** 처음에 짧고 넓은 쿼리로 전체 윤곽을 파악한 다음 좁혀나가는 것이 효과적이다. 처음부터 너무 좁은 쿼리는 결과가 없거나 편향된다.
- **병렬 도구 호출이 처리 시간을 90%까지 단축할 수 있다.** 리드가 서브 에이전트 3~5개를 동시에 실행하고, 각 서브 에이전트도 도구 3개 이상을 동시에 호출하면 된다.
- **도구 결과를 받은 후 "생각하는 토큰(thinking tokens)"을 끼워 넣는 것(Interleaved thinking)이 적응적 행동에 결정적이다.** AI가 결과를 받고 나서 다음 행동을 정하기 전에 잠깐 추론할 시간을 주는 것.

### 안티패턴 — Anthropic 본인들이 직접 겪은 실수들

- 단순한 쿼리에 서브 에이전트를 50개나 생성한 것.
- 존재하지 않는 소스를 끝없이 탐색하게 한 것.
- 서브 에이전트끼리 과도하게 업데이트를 주고받아 서로를 방해한 것.

---

## 4. 2025 업데이트 — Context Engineering (컨텍스트 공학)

_출처: Effective context engineering, 2025-09_

### 새로운 핵심 개념 — "컨텍스트를 어떻게 구성할 것인가"

> "컨텍스트 공학은 프롬프트 공학의 자연스러운 발전이다... 어떤 컨텍스트 구성이 모델이 원하는 행동을 가장 잘 하게 만드는가?" — _Context engineering post_

프롬프트(AI에게 던지는 질문/지시)만 잘 쓰던 시대에서, **AI에게 보여주는 정보(컨텍스트) 자체를 큐레이션하는 시대**로 넘어왔다. 에이전트 루프는 매 턴마다 새로운 토큰(정보)을 만들어내는데, 이걸 어떻게 솎아낼지가 성능을 결정한다.

### Context Rot — 컨텍스트도 오염된다

- 트랜스포머 AI는 입력 길이의 제곱(n²)에 비례하는 계산을 한다. 컨텍스트가 길수록 AI의 주의(attention)가 흩어진다.
- AI 모델이 입력이 길어질수록 약해지는 이유: 학습 데이터 자체가 짧은 시퀀스 위주였기 때문.
- "성능이 갑자기 뚝 떨어지는 절벽이 아니라, 서서히 닳는 경사면이다" — 갑자기 망가지진 않지만 정확도가 점점 떨어진다.

### Right Altitude — 너무 빡빡하지도, 너무 헐겁지도 않게

- **너무 빡빡한 쪽**: if-else를 하드코딩한 프롬프트 → 조금만 달라져도 깨지고, 유지보수 지옥.
- **너무 헐거운 쪽**: "잘 알아서 해줘" 식의 모호한 고수준 가이드 → AI가 추측으로 채운다.
- **Goldilocks(딱 좋은 지점)**: 행동을 충분히 안내하되, AI가 스스로 판단할 여지를 남긴다.

### Just-in-Time Context — 필요할 때 딱 꺼내는 방식

예전(RAG 방식): 관련 데이터를 미리 전처리해서 컨텍스트에 미리 다 넣어두었다.

새 방식: **가벼운 식별자**(파일 경로, 쿼리 ID, URL)만 들고 있다가, AI가 실행 중에 도구로 동적으로 불러온다.

실제 예시인 Claude Code를 보면:

- `CLAUDE.md` (프로젝트 규칙 파일)는 미리 로드.
- `glob`(파일 찾기), `grep`(내용 검색)은 필요할 때 just-in-time으로 실행. → **둘을 섞은 하이브리드** 방식.

이건 인간의 인지와 똑같다 — 우리는 모든 걸 외우지 않고 파일 시스템, 받은 메일함, 북마크로 색인해두고 필요할 때 꺼낸다.

### 긴 작업을 위한 3가지 기법

| 기법                                       | 정의                                                                                  | 언제 강한가                                    |
| ------------------------------------------ | ------------------------------------------------------------------------------------- | ---------------------------------------------- |
| **Compaction (압축)**                      | 컨텍스트 창이 꽉 차기 전에 지금까지의 내용을 요약하고, 새 창에서 이어간다             | 대화가 앞뒤로 오가는(back-and-forth) 흐름일 때 |
| **Structured note-taking (구조화된 메모)** | 외부 파일(NOTES.md, progress.txt)에 메모를 쓰고 필요할 때 다시 불러온다               | 명확한 마일스톤이 있는 반복 작업일 때          |
| **Sub-agent architecture (서브 에이전트)** | 하위 AI가 깨끗한 컨텍스트로 깊이 작업하고, 1~2천 토큰짜리 요약만 리드 AI에게 반환한다 | 병렬 탐색이 의미 있을 때                       |

> "원하는 결과가 나올 가능성을 최대화하는, 가장 적은 수의 고신호(high-signal) 토큰을 찾아라." — _Context engineering post_ (대원칙)

### 도구 설계 — Anthropic이 가장 강조하는 실전 팁

- **도구가 지나치게 많은 것이 가장 흔한 실패 원인이다.** "사람 엔지니어가 이 상황에 어떤 도구를 써야 할지 즉각 대답 못 하면, AI도 못 한다."
- 도구는 self-contained(스스로 완결)되고, 견고하며, 의도가 명확해야 한다.
- 입력 파라미터는 설명적이고 모호하지 않아야 한다.
- **AI 입장에서 생각하기** — 주니어 개발자에게 설명하듯 docstring을 써라.
- 파라미터 이름과 설명을 바꿔서 실수하기 어렵게 만들어라 (실수 방지 설계, poka-yoke).
- 도구 정의는 프롬프트 엔지니어링만큼의 노력을 들여야 한다.

---

## 5. 2025 업데이트 — Long-Running Agent Harness (장기 실행 에이전트 구조)

_출처: Effective harnesses for long-running agents, 2025-11_

### 문제

- 에이전트가 여러 컨텍스트 창을 가로질러서 일관되게 진행해야 할 때가 있다.
- Compaction(압축)만으로는 부족하다. Anthropic의 가장 강력한 모델인 Opus 4.5조차 "claude.ai 클론을 만들어줘" 같은 고수준 프롬프트 하나만 주면 실패한다.
- 두 가지 실패 패턴:
  1. **한 번에 다 하려는 시도(One-shot)** → 컨텍스트를 다 써서 절반만 구현하고 문서화도 없이 끝남.
  2. **너무 이른 완료 선언** → "진행된 흔적"만 보고 "다 끝났네"라고 착각.

### 해법: 2단계 에이전트 구조

#### Initializer agent (초기화 에이전트) — 딱 1번만 실행

- `init.sh` 작성 (개발 서버를 실행하는 쉘 스크립트).
- `claude-progress.txt` 생성 (이후 모든 에이전트가 기록하는 로그 파일).
- **JSON feature list** 작성 (예: claude.ai 클론에 필요한 기능 200개 이상을 나열하고, 각 기능의 `passes: false`로 초기화).
- 초기 git commit으로 기준점(baseline) 설정.

#### Coding agent (코딩 에이전트) — 반복 실행

매 세션 시작 시:

1. `pwd` (현재 위치 확인)
2. `claude-progress.txt` 읽기
3. `feature_list.json` 읽기
4. git log 확인
5. `init.sh` 실행
6. End-to-end smoke test (전체 동작 검증)

그리고: **한 번에 딱 하나의 기능(feature)만 작업**.

매 세션 끝에: 설명이 담긴 git commit + progress.txt 업데이트.

### 왜 JSON feature list인가

- 실험 결과, 모델이 마크다운 파일보다 **JSON 파일을 함부로 수정하지 않는다**.
- "테스트를 제거하거나 수정하는 것은 절대 허용되지 않는다" 같은 강한 지시와 결합.
- `passes` 항목의 boolean 값 하나만 바꾸도록 강제.

### End-to-End 검증의 중요성

명시적으로 지시하지 않으면, Claude는 "사람처럼 실제로 사용해보는" 검증을 하지 않는다. unit test나 curl 요청만 돌리고 통과 처리해버린다.

Puppeteer MCP 같은 브라우저 자동화 도구를 주고 "실제 사용자처럼 검증해라"고 지시하면 성능이 급격히 올라간다.

### 핵심 통찰 — 3개의 글에 공통으로 깔린 원칙

> "AI 에이전트를 만들 때, 마지막 1마일이 전체 여정의 대부분이 되는 경우가 많다... 에이전트 시스템에서 오류가 복합적으로 쌓이는 특성 때문에, 일반 소프트웨어에서는 사소한 문제가 에이전트를 완전히 탈선시킬 수 있다." — _Multi-agent post_

- 프로토타입에서 실제 서비스로 넘어가는 격차가 예상보다 훨씬 크다.
- 작은 버그 하나가 시스템 전체의 방향을 바꿀 수 있다.
- 그래서 **실패 지점에서 재개(resume from failure) / 체크포인트 / rainbow deployment**가 필수다.

---

## 6. 2025 업데이트 — Agent Skills (에이전트 스킬)

_출처: Agent Skills 발표 (Dec 2025, 개방 표준)_

### 정의

- **SKILL.md 파일**이 들어있는 디렉토리. 에이전트가 동적으로 발견하고 불러올 수 있는 능력(capability) 패키지.
- 일반적인 AI 에이전트를 → 특정 도메인에 특화된 AI 에이전트로 변환해주는 **이식 가능하고 조합 가능한 단위**.

### 어디에 쓰나

- 도메인별 best practice(모범 사례)를 한 폴더에 묶어둔다 (예: pptx skill, docx skill, pdf skill).
- AI 에이전트가 작업에 맞는 스킬을 자동으로 선택해서 SKILL.md를 읽고 따른다.
- 스킬은 **함수처럼 호출 가능** — 서브 에이전트와는 다른 개념이다. (서브 에이전트는 별도의 컨텍스트 창을 가진 독립 AI 인스턴스.)

### Skill vs. Sub-agent vs. Tool — 세 가지 비교

|           | Skill (스킬)                          | Sub-agent (서브 에이전트)               | Tool (도구)      |
| --------- | ------------------------------------- | --------------------------------------- | ---------------- |
| 정의      | 모범 사례 묶음 (SKILL.md + 스크립트)  | 별도 컨텍스트 창을 가진 Claude 인스턴스 | 단일 함수        |
| 용도      | "이 도메인은 이렇게 해라"는 지식 전달 | 병렬로 깊이 탐색                        | 외부 시스템 호출 |
| 비용      | 낮다 (md 파일 한 번 읽으면 끝)        | 높다 (완전한 AI 추론 실행)              | 낮다             |
| 격리 여부 | 없음 (현재 컨텍스트에 로드)           | 있음 (깨끗한 독립 컨텍스트)             | 없음             |

---

## 7. 결정 트리 — 무엇을 언제 쓸까

아래 흐름을 따라가면서 지금 상황에 어떤 패턴이 맞는지 결정해라.

```
입력 작업
  │
  ├─ 단일 LLM 호출로 끝나나? ── YES → Augmented LLM (도구 + 메모리 + retrieval)
  │
  ├─ 단계가 명확히 N개로 쪼개지나? ── YES → Prompt Chaining (gate 포함)
  │
  ├─ 입력이 종류별로 뚜렷이 다른가? ── YES → Routing (모델/prompt 분기)
  │
  ├─ 같은 작업 다관점·병렬로 신뢰도 ↑? ── YES → Parallelization (sectioning/voting)
  │
  ├─ 평가 기준이 명확하고 반복 개선이 가치? ── YES → Evaluator-Optimizer
  │
  ├─ 하위작업의 수·모양을 모르나?
  │     │
  │     ├─ value > 15× 토큰 비용? & 본질적 병렬? ── YES → Orchestrator-Workers (multi-agent)
  │     │
  │     └─ 그 외 ── single agent + 좋은 도구 + just-in-time context
  │
  └─ 작업이 여러 session에 걸치나? ── 추가로 Long-running harness 적용
        (initializer + coding agent + progress.txt + JSON feature list)
```

---

## 8. 안티패턴 — Anthropic이 명시적으로 경고한 것들

이것들은 "하지 말라"는 게 아니라, "이렇게 하면 왜 안 되는지"를 이해하고 피하는 것이 목적이다.

1. **프레임워크부터 잡기** → LangChain 같은 추상 계층이 프롬프트/응답을 가려서 디버깅이 지옥이 된다. **LLM API 직접 호출부터 시작해라**.
2. **도구를 너무 많이 만들기 (bloated tool set)** → AI가 어떤 도구를 써야 할지 고를 수 없게 된다.
3. **단순 쿼리에 멀티 에이전트 → 서브 에이전트 50개 생성** → 비용만 폭발하고 성능은 떨어진다.
4. **서브 에이전트에게 짧은 지시** ("X를 리서치해줘") → 중복 작업과 누락이 발생한다.
5. **모든 데이터를 미리 로드 (heavy RAG)** → 컨텍스트가 오염(context rot)되고, 비용이 올라간다. just-in-time 방식이 더 강하다.
6. **강제로 지켜야 할 상태(state)를 마크다운 파일에 저장** → AI가 자유롭게 덮어쓰기 때문에 상태가 날아간다. **JSON을 써라**.
7. **End-to-end 검증을 안 시킴** → unit test만 돌리고 끝난 것으로 처리. **브라우저 자동화로 실제 사람처럼 검증하게 해라**.
8. **에러 발생 시 에이전트를 처음부터 재시작** → 비싸고 사용자 경험이 나빠진다. **resume(재개) + checkpoint(체크포인트) 구조를 써라**.

---

## 9. 3가지 핵심 원칙 (Dec 2024 → 2025 보강 후)

처음에 Anthropic이 제시한 3가지 원칙을 2025년에 3개 더 추가해서 총 6개가 되었다.

> **원본 3가지 (Dec 2024)**:
>
> 1. 단순함을 유지해라 (Maintain simplicity).
> 2. 투명성을 우선시해라 (Prioritize transparency) — 계획 단계를 사람이 볼 수 있게 노출해라.
> 3. ACI(에이전트-컴퓨터 인터페이스)를 신중하게 설계해라 — 도구 문서화 + 테스트.

**2025년 추가된 3가지**:

4. **컨텍스트를 유한한 자원으로 다뤄라** — 최소한의 필수 컨텍스트, just-in-time 로딩, 구조화된 메모 활용.
5. **장기 실행을 고려해서 설계해라** — initializer 에이전트 + progress 파일 + git을 메모리로 활용 + end-to-end 검증.
6. **멀티 에이전트는 토큰 경제학의 결정이다** — 작업 가치 > 토큰 비용 × 15배일 때만 쓴다.

---

## 10. DH Case Study에 적용 — Agentic IDE Session Backend

DH의 케이스 스터디(`AGENTS.md-aware Agentic IDE Session Backend`)에 위 원칙들을 매핑한 결과.

### 추천 아키텍처: 워크플로우 뼈대 + 작은 에이전트 루프 1개

```
[POST /sessions/:id/plan]
        │
        ▼
[Parser: AGENTS.md + brand rules]      ← 결정적(deterministic) — 코드가 처리
        │
        ▼
[LLM: PlanStep 분해]                    ← 비결정적(non-deterministic) — AI가 처리, 스키마로 출력 형식 고정
        │
        ▼
[Validator: 각 step의 target_files]    ← 결정적 — 코드가 검증

[POST /sessions/:id/patches]
        │
        ▼
[LLM: PatchProposal (diff)]            ← 비결정적 — AI가 코드 수정안 생성
        │
        ▼
[Guardrail: forbidden pattern + AGENTS rule check]   ← 결정적 — 금지 패턴 필터링
        │
        ▼
[저장 + audit log + traceId]

[POST /sessions/:id/run-tests]
        │
        ▼
[Test runner + 결과 저장]              ← 결정적
```

이 구조를 **"결정적 샌드위치(deterministic sandwich)"** 라고 부른다. AI 호출 양쪽을 결정적인 코드가 감싸는 형태.

### 왜 이런 결정을 내렸나 (4시간 budget 안에서)

| 결정                                                                                 | 이유                                                                          | 이 결정을 뒤집을 조건                                                     |
| ------------------------------------------------------------------------------------ | ----------------------------------------------------------------------------- | ------------------------------------------------------------------------- |
| **멀티 에이전트 안 쓴다**                                                            | 코딩 도메인 + 단일 세션 = 멀티 에이전트가 오히려 손해. 토큰 15배, 협의 필요 ↑ | 세션이 multi-repo로 확장되고 병렬 분석이 의미 있어지면 서브 에이전트 도입 |
| **에이전트 루프는 patch 생성 단계에만**                                              | 거기만 진짜로 비결정적(AI 판단이 필요). 나머지는 워크플로우로 충분            | LLM이 plan 단계에서도 도구를 동적으로 골라야 하면 plan도 에이전트로       |
| **Just-in-time context 사용** (AGENTS.md는 파일 경로로만 들고 있다가 필요할 때 읽기) | RAG 미리 로드 안 해도 파일 크기가 작음. 인덱싱이 오래되는(stale) 위험 없음    | 규칙 수가 1000개 이상 되면 벡터 검색 도입                                 |
| **JSON in / JSON out (결정적 샌드위치)**                                             | LLM 호출 양 끝이 결정적 → 테스트하기 쉽고, AI 모델 교체도 쉬움                | 자유 텍스트 출력이 본질인 단계 (예: PR description 생성)                  |
| **Compaction은 P2(나중에)**                                                          | 단일 세션 4시간 안에 컨텍스트가 넘칠 일이 거의 없다                           | 세션이 수 시간 이상으로 늘어나면 progress.txt + compaction 도입           |
| **Skills (SKILL.md) 도입은 P2 — README에 언급만**                                    | 4시간 안에는 브랜드 룰 1개를 하드코딩하는 게 더 빠름                          | 브랜드·규칙 수가 늘면 브랜드별 SKILL.md로                                 |

### 합격권 시그널 — 이 결정들이 README에 명시되어야 할 곳

- **Architecture 섹션**: deterministic-sandwich 다이어그램.
- **Trade-offs 섹션**: 위 표 그대로.
- **AI Leverage 섹션**: 단일 에이전트 루프가 patch 단계에만 박혀있다는 것.
- **Not Done 섹션**: multi-agent / compaction / Skills를 의도적으로 미뤘다(deferral)는 것.
- **Observability 한 줄**: traceId + audit log.

### DH 평가자가 실제로 보는 것 (JD 분석 기반)

**핵심 진단**: DH가 case study에서 보고 싶어하는 건 "거대한 autonomous agent를 만들 수 있는가"가 아니다. **"engineer workflow를 agentic하게 설계할 수 있는가"** 다. JD 키워드(IDE/CLI, workflow, context integration, guardrails, developer productivity, orchestration, deterministic safety)가 이 방향을 가리킨다.

#### 가능성 높은 case study 시나리오 Top 5

| 시나리오                                                                                                     | JD 근거                                              | 우리 정본 시나리오와의 관계                |
| ------------------------------------------------------------------------------------------------------------ | ---------------------------------------------------- | ------------------------------------------ |
| **CLI 기반 coding assistant** (예: "generate migration plan" → plan + changed files + commands + validation) | IDE/CLI, developer workflow, contextual intelligence | Session API 자체로 포섭                    |
| **Internal context-aware agent** (Slack + docs + codebase → 관련 컨텍스트 → 구현 제안)                       | documentation, Slack, GDrive integration             | AGENTS.md + brand rules 입력으로 mock 처리 |
| **Guardrail / validation system** (LLM 생성 코드 → validate → 위험한 출력 reject)                            | "generated code is safe to deploy"                   | GuardrailCheck 모델 — 그대로               |
| **Multi-step agent workflow** (Task → planner → executor → validator)                                        | 상태 관리, retry, deterministic boundary             | Plan → Patch → Test 흐름                   |
| **DevEx tooling** (PR summarizer, migration assistant, CI failure analyzer)                                  | git worktrees 직접 언급                              | README의 rollout 섹션에 언급               |

→ 우리 정본 시나리오 (`AGENTS.md-aware Agentic IDE Session Backend`)가 **위 5개를 다 포섭**한다. 시나리오 변경 불필요.

#### "기술보다 더 중요할 수 있는" 평가 요소 7개

| 요소                       | 왜 중요한가               | README에 어떻게 박나                             |
| -------------------------- | ------------------------- | ------------------------------------------------ |
| **scope control**          | 4시간 제한이 본질         | P0/P1/P2 명시 + Not Done 섹션                    |
| **explicit assumptions**   | AI-native thinking 시그널 | Assumption 섹션에 5개+                           |
| **reversible decisions**   | 실무 감각 시그널          | Trade-off의 "Reconsider if W"                    |
| **deterministic boundary** | hallucination 제어 능력   | Architecture의 deterministic-sandwich 다이어그램 |
| **architecture clarity**   | orchestration 이해도      | 1단락 + 다이어그램 30초 안에 이해 가능하게       |
| **failure handling**       | production mindset        | guardrail + retry + audit log 한 줄씩            |
| **README quality**         | communication 능력        | 5섹션 + 톤 6원칙 (P0-1)                          |

#### "AI-native engineer" 시그널 박는 핵심 문장 3개

이 톤이 베인 문장이 README에 한두 개 박히면 평가자가 즉시 시그널 잡는다.

```
Architecture 첫 문장:
"This service converts implicit human debugging workflows into explicit,
observable agent workflows — the LLM proposes, deterministic checks decide."
```

```
AI Leverage / Verification:
"The LLM only performs extraction.
Merging and validation are deterministic."
```

```
Trade-off (4시간 제약을 의식적 결정으로):
"I intentionally skipped caching because prompt iteration speed mattered
more than throughput within the 4h constraint."
```

→ 이 3개 문장 결은 **Karrot anomaly reasoner 영어 스토리(P5-1) 1분 버전 첫 문장**으로도 그대로 재활용. 면접 일관성을 위해 동일한 framing 사용.

#### 합격권 3개 키워드는 여전히 위 분석에 빠짐 (보강 필요)

위 시나리오 분석은 일반 agentic AI 회사용으론 100점이지만 **DH 특화 시그널은 약하다**. 다음은 케이스 스터디에 반드시 박혀야 한다 — 빠지면 70점, 들어가면 합격권:

- **AGENTS.md / Engineering Manifesto context** — JD 직격 키워드. 평가자가 키워드 매칭으로 잡는다.
- **Multi-brand override** (efood / glovo / talabat) — DH 정체성. brand 필드 한 줄 + brand별 rule override 한 줄로 충분.
- **Smart Guardrails with severity** — 단순 reject가 아니라 severity / reason / ruleId가 들어간 GuardrailCheck.

---

## 11. 이 문서가 다루지 않는 것 (솔직한 한계)

- **MCP 서버 구현 디테일** — 별도 문서가 필요. 여기서는 도구 설계 원칙까지만 다룬다.
- **Anthropic 외 벤더의 패턴** (OpenAI Assistants, LangGraph 등) — DH가 Claude를 쓸 가능성이 높아 Anthropic-first로 작성했다.
- **모델별 latency·비용 숫자** — 빠르게 바뀌므로 결정 시점에 별도 확인 필요.
- **Eval harness 구축 디테일** — Multi-agent 글의 LLM-as-judge 원칙만 인용. 실제 루브릭 설계는 별도 작업.
- **Security / sandbox** — 에이전트에게 코드 실행 권한을 줄 때의 격리 문제는 별도 영역.

---

## 12. 참고 (정본 출처)

- [Building Effective Agents (2024-12)](https://www.anthropic.com/research/building-effective-agents)
- [How we built our multi-agent research system (2025-06)](https://www.anthropic.com/engineering/multi-agent-research-system)
- [Effective context engineering for AI agents (2025-09)](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Effective harnesses for long-running agents (2025-11)](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents)
- [Building agents with the Claude Agent SDK](https://www.anthropic.com/engineering/building-agents-with-the-claude-agent-sdk)
- [Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic Cookbook — patterns for agents and basic workflows](https://platform.claude.com/cookbook/patterns-agents-basic-workflows)

---

---

## 13. Cookbook 실전 코드 분석

_출처: [anthropics/claude-cookbooks — patterns/agents](https://github.com/anthropics/claude-cookbooks/tree/main/patterns/agents)_

"Building Effective Agents" 블로그 포스트의 **공식 레퍼런스 구현체**다. 패턴의 개념이 아니라 실제로 어떻게 코드로 짜는지를 보여준다. 최소한의 코드(minimal implementation)로 핵심만 담았다.

### 파일 구조

```
patterns/agents/
├── README.md
├── util.py                       ← 공통 유틸 (API 호출 wrapper + XML 파서)
├── basic_workflows.ipynb         ← Prompt Chaining / Parallelization / Routing
├── evaluator_optimizer.ipynb     ← Evaluator-Optimizer 루프
├── orchestrator_workers.ipynb    ← Orchestrator-Workers 패턴
└── prompts/
    ├── citations_agent.md        ← 인용 추가 전용 에이전트 프롬프트
    ├── research_lead_agent.md    ← 리서치 리드(오케스트레이터) 프롬프트
    └── research_subagent.md      ← 리서치 서브 에이전트 프롬프트
```

---

### `util.py` — 공통 유틸리티

모든 notebook이 공유하는 딱 두 가지 함수.

```python
def llm_call(prompt, system_prompt="", model="claude-sonnet-4-6") -> str:
    # Claude API를 한 번 호출하고 텍스트 응답을 반환
    # 기본 모델: claude-sonnet-4-6, temperature: 0.1 (낮게 설정 = 안정적인 출력)

def extract_xml(text, tag) -> str:
    # AI 응답에서 <tag>내용</tag>을 뽑아내는 regex 함수
    # 예: extract_xml(response, "selection") → 라우팅 결과 파싱
```

**왜 XML인가?** AI가 구조화된 데이터를 출력할 때 JSON보다 XML 태그가 더 안정적으로 파싱된다는 것이 Anthropic의 실험 결과다. 태그가 깨질 위험이 낮고, 부분 파싱도 쉽다.

---

### `basic_workflows.ipynb` — 3가지 기본 패턴의 최소 구현

#### 1. Prompt Chaining — `chain()` 함수

```python
def chain(input: str, prompts: list[str]) -> str:
    result = input
    for i, prompt in enumerate(prompts, 1):
        result = llm_call(f"{prompt}\nInput: {result}")  # 이전 결과를 다음 입력으로
    return result
```

핵심: 단 5줄. 이전 단계 결과가 다음 단계의 입력이 된다.

**실전 예시**: 분기 보고서 텍스트 → 숫자만 추출 → 퍼센트로 변환 → 내림차순 정렬 → 마크다운 테이블로 변환. 각 단계가 명확히 하나의 변환만 담당한다.

#### 2. Parallelization — `parallel()` 함수

```python
def parallel(prompt: str, inputs: list[str], n_workers: int = 3) -> list[str]:
    with ThreadPoolExecutor(max_workers=n_workers) as executor:
        futures = [executor.submit(llm_call, f"{prompt}\nInput: {x}") for x in inputs]
        return [f.result() for f in futures]
```

핵심: `ThreadPoolExecutor`로 여러 AI 호출을 동시에 실행. 순서를 보장하면서도 병렬로 처리된다.

**실전 예시**: 고객 / 직원 / 투자자 / 공급자 4개 이해관계자 그룹에 대해 "시장 변화가 이 그룹에 어떤 영향을 주는가"를 동시에 분석.

#### 3. Routing — `route()` 함수

```python
def route(input: str, routes: dict[str, str]) -> str:
    # 1단계: AI한테 어느 경로로 보낼지 먼저 물어봄
    selector_prompt = f"사용 가능한 경로: {list(routes.keys())} 중에서 선택하고 <selection>태그에 담아 반환"
    route_key = extract_xml(llm_call(selector_prompt), "selection").strip().lower()

    # 2단계: 선택된 specialized 프롬프트로 실제 처리
    return llm_call(f"{routes[route_key]}\nInput: {input}")
```

핵심: AI 호출이 두 번 일어난다. 첫 번째는 "어느 경로?"를 결정하고, 두 번째는 그 경로의 전문 프롬프트로 실제 처리.

**실전 예시**: 고객 지원 티켓을 `billing` / `technical` / `account` / `product` 중 하나로 분류하고, 각 팀 전용 지침으로 응답 생성.

---

### `evaluator_optimizer.ipynb` — Generate → Evaluate → 루프

```python
def loop(task, evaluator_prompt, generator_prompt):
    memory = []
    thoughts, result = generate(generator_prompt, task)  # 첫 번째 생성
    memory.append(result)

    while True:
        evaluation, feedback = evaluate(evaluator_prompt, result, task)
        if evaluation == "PASS":
            return result  # 합격하면 종료

        # 이전 시도들과 피드백을 context에 쌓아서 재시도
        context = "이전 시도들:\n" + "\n".join(memory) + f"\n피드백: {feedback}"
        thoughts, result = generate(generator_prompt, task, context)
        memory.append(result)
```

핵심 구조:

- Generator 출력 형식: `<thoughts>내 이해와 계획</thoughts><response>실제 결과</response>`
- Evaluator 출력 형식: `<evaluation>PASS / NEEDS_IMPROVEMENT / FAIL</evaluation><feedback>이유</feedback>`
- **이전 시도들이 누적되어 context에 들어간다** — AI가 같은 실수를 반복하지 않도록.

**실전 예시**: Stack 자료구조 구현 (push/pop/getMin 모두 O(1)) — 코드 정확성 + 시간복잡도 + 스타일 세 가지 기준으로 평가.

---

### `orchestrator_workers.ipynb` — `FlexibleOrchestrator` 클래스

#### 동작 흐름

```
1. Orchestrator 호출
   → 작업 분석 후 XML로 서브태스크 정의
   <tasks>
     <task><type>formal</type><description>기술적이고 정확한 버전</description></task>
     <task><type>conversational</type><description>친근하고 읽기 쉬운 버전</description></task>
   </tasks>

2. parse_tasks()로 XML 파싱 → [{"type": "formal", "description": "..."}, ...]

3. 각 Worker 호출 (원본 task + 담당 subtask 둘 다 전달)
   → 각자 <response>태그에 결과 반환
```

**핵심 설계 결정 — Worker에게 원본 task도 함께 준다:** Worker가 자기 subtask만 받으면 전체 맥락을 잃는다. "원본 과제가 뭔지" + "내가 담당할 스타일이 뭔지" 둘 다 알아야 좋은 결과가 나온다.

**비용 최적화 힌트** (notebook에서 직접 언급): Orchestrator는 Claude Opus, Worker는 Claude Haiku. 복잡한 계획은 강력한 모델이, 실행은 저렴한 모델이 담당.

---

### `prompts/` — 실제 Anthropic 연구 시스템의 프롬프트

이 세 파일은 단순한 예시가 아니라, Anthropic이 **실제 내부 리서치 시스템**에서 사용하는 프롬프트다. 구조와 사고방식을 그대로 참고할 수 있다.

#### `research_lead_agent.md` — 리드(오케스트레이터) 프롬프트

**쿼리 타입을 3가지로 분류한 다음 전략을 다르게 쓴다:**

| 타입                | 정의                                           | 예시                                   | 서브에이전트 전략                                                |
| ------------------- | ---------------------------------------------- | -------------------------------------- | ---------------------------------------------------------------- |
| **Depth-first**     | 하나의 주제를 여러 관점에서 깊게 파고드는 경우 | "우울증 치료법 중 가장 효과적인 것은?" | 각 에이전트가 다른 관점(유전적/환경적/심리적)으로 같은 질문 탐색 |
| **Breadth-first**   | 여러 독립적인 하위 질문으로 쪼개지는 경우      | "EU 국가들의 세금 시스템 비교"         | 각 에이전트가 다른 국가를 맡아 독립적으로 리서치                 |
| **Straightforward** | 단순 사실 찾기, 단일 리소스로 해결 가능        | "도쿄의 현재 인구는?"                  | 서브에이전트 1개, 리드와 반반 분업                               |

**서브에이전트 수 가이드라인:**

- 단순: 1개
- 표준: 2~3개
- 중간: 3~5개
- 복잡: 5~10개 (최대 20개 — 초과하면 접근 방식 재구성)

**중요한 원칙**: 리드는 직접 리서치하는 게 아니라 **계획 → 위임 → 합성**이 역할. 서브에이전트 지시는 "이대로 따라하면 훌륭한 답이 나올 수 있을 만큼" 상세하게.

#### `research_subagent.md` — 서브 에이전트 프롬프트

**OODA 루프 기반 리서치 프로세스:**

- **O**bserve: 지금까지 뭘 모았나, 뭐가 아직 없나, 어떤 도구가 있나
- **O**rient: 어떤 도구와 쿼리가 필요한 정보를 가장 잘 가져올까
- **D**ecide: 구체적인 도구 사용 결정
- **A**ct: 도구 실행

**도구 호출 예산(tool call budget):**

- 단순 질문: 5회 이하
- 중간 질문: 5회
- 어려운 질문: ~10회
- 매우 어려운 질문: 최대 15회
- **절대 최대: 20회** — 초과 시 리포트 작성으로 전환

**소스 품질 판단 기준**: 뉴스 aggregator보다 원본 소스 우선, 수동태+익명 출처 조심, 마케팅 언어와 추측성 미래 예측 주의.

#### `citations_agent.md` — 인용 추가 전용 에이전트 프롬프트

가장 제약이 엄격한 프롬프트. 핵심 규칙:

- **원문을 1글자도 수정하지 마라** — 공백까지 100% 동일하게 유지
- 인용이 필요 없는 문장엔 달지 마라 (과잉 인용 금지)
- 같은 소스에서 여러 인용을 한 문장에 넣지 마라 (문장 끝에 한 번만)
- 출력: `<exact_text_with_citation>...</exact_text_with_citation>` 태그 안에 담기

이 에이전트가 별도로 존재하는 이유: 리포트 생성과 인용 추가를 분리하면, 리포트 생성 에이전트가 "인용을 어떻게 달까"를 신경 쓰지 않아도 되어서 더 좋은 글을 쓸 수 있다. **단일 책임 원칙**의 적용.

---

### Cookbook에서 배우는 핵심 설계 원칙

1. **XML으로 구조화된 출력** — AI 응답을 파싱할 때 JSON보다 XML 태그가 더 안정적.
2. **최소 구현(minimal implementation)** — chain()이 5줄인 것처럼, 개념 검증엔 단순하게.
3. **Worker에게 원본 context도 함께** — subtask만 주지 말고 "왜 이걸 하는지"까지 전달.
4. **역할 분리** — 생성 / 평가 / 인용 추가를 별도 에이전트로 분리 (단일 책임).
5. **쿼리 타입 먼저 분류** — Depth-first냐 Breadth-first냐에 따라 에이전트 배분 전략이 완전히 달라진다.
6. **리드는 실행하지 않는다** — 리드의 역할은 계획·위임·합성. 직접 리서치는 최소화.

> **Companion docs (이 vault 안)**:
>
> - [코코 셀프 트레이닝 프롬프트.md](코코 셀프 트레이닝 프롬프트.md) — 4일 일정 정본
> - [README 5섹션 영어 템플릿 (P0-1).md](README 5섹션 영어 템플릿 (P0-1).md) — case study README 골격
> - [평가자 시각 — 인재상 & 채점 루브릭.md](평가자 시각 — 인재상 & 채점 루브릭.md) — 5축 가중치
> - [WHY 분해 노트 — 표면 vs 본질.md](WHY 분해 노트 — 표면 vs 본질.md) — Y톤 self-check
