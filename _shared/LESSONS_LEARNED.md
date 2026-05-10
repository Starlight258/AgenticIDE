# Lessons Learned — Agentic IDE Take-Home Sessions

> Updated after each session. Read this before starting Phase 3 implementation.

---

## Session: case-01-session-backend (2026-05-08)

### Mistake 1 — Agent에게 위임 후 `load_dotenv()` 누락

**무슨 일**: Agent A가 `src/main.py`를 작성할 때 `load_dotenv()`를 누락했다.
`.env`에 API 키가 있었는데도 서버가 mock 모드로 동작했고, 실제 LLM 호출이 안 된다고 착각했다.

**왜 발생**: Agent prompt에 "dotenv를 로드하라"는 명시적 지시가 없었다.
merge 후 cross-cutting concern (env loading, logging config) 검토를 하지 않았다.

**다음에 할 것**:
- Agent A prompt에 반드시 명시: `"from dotenv import load_dotenv; load_dotenv()` must be the first thing in main.py, before any other local imports"`
- Merge 직후 체크리스트: `grep -r "load_dotenv" src/` → 없으면 즉시 추가

---

### Mistake 2 — `max_tokens=1024`로 LLM 응답 잘림

**무슨 일**: `generate_list()` 응답이 1024 토큰을 초과해서 JSON이 중간에 잘렸다.
`JSONDecodeError: Unterminated string` 발생.

**왜 발생**: "짧은 응답이면 충분하겠지"라고 가정했다.
실제로는 PlanStep 배열 + 설명문이 1024 토큰을 넘는 경우가 흔하다.

**다음에 할 것**:
- LLM 호출 시 `max_tokens`는 항상 **4096** 이상으로 시작한다.
- 특히 list 반환 함수는 더 크게 잡는다 (8192도 괜찮다, 출력 토큰 과금이지 입력 아님).

---

### Mistake 3 — 자유 텍스트 JSON 파싱이 불안정 (tool_use 안 쓴 것)

**무슨 일**: 시스템 프롬프트에 "JSON으로만 응답해"라고 지시했지만,
Claude가 응답을 ` ```json ... ``` ` 마크다운으로 감싸서 반환했다.
`json.loads(raw)` 실패 → `_parse_json()` 코드펜스 제거 로직 추가 → 그래도 응답 잘림으로 실패.

**왜 발생**: 처음부터 Anthropic SDK의 `tool_use` (structured output) 를 쓰지 않았다.
"프롬프트로 JSON 유도"는 항상 불안정하다. Claude는 마크다운으로 감싸거나, 설명문을 붙이거나, 토큰 제한에 걸리면 JSON을 잘라버린다.

**다음에 할 것**:
- **LLM에서 구조화된 출력이 필요하면 항상 `tool_use`를 쓴다.** 예외 없음.
- 올바른 패턴:
  ```python
  response = client.messages.create(
      model="claude-sonnet-4-6",
      max_tokens=4096,
      tools=[{"name": "output", "description": "...", "input_schema": schema.model_json_schema()}],
      tool_choice={"type": "tool", "name": "output"},
      messages=[...],
  )
  result = response.content[0].input  # 이미 dict, json.loads 불필요
  ```
- list 반환이 필요하면 wrapper schema 사용:
  ```python
  list_schema = {
      "type": "object",
      "properties": {"items": {"type": "array", "items": schema.model_json_schema()}},
      "required": ["items"],
  }
  # → result["items"] 로 꺼냄
  ```

---

### Mistake 4 — E2E 검증 스크립트에서 false negative

**무슨 일**: `curl | python3 -c "import json; print(json.load(sys.stdin)[0]['id'])"` 가
JSON 문자열 안에 `\n`이 있을 때 `Invalid control character` 에러를 냈다.
서버는 정상인데 검증 스크립트가 실패해서 "서버가 broken"으로 오판했다.

**왜 발생**: bash 파이프로 JSON을 python3 인라인 코드에 넘기면 제어문자 처리가 취약하다.
특히 diff나 코드가 포함된 응답에서 자주 발생한다.

**다음에 할 것**:
- E2E 검증 시 항상 **파일로 받아서 파싱**하거나 `python3 -m json.tool`로 출력 확인만 한다.
  ```bash
  curl -s ... -o /tmp/response.json
  python3 -c "import json; d=json.load(open('/tmp/response.json')); print(d['id'])"
  ```
- 또는 `jq`가 있으면: `curl -s ... | jq '.[0].id'`
- 서버 로그에서 HTTP 200이 나오면 서버는 정상. 스크립트 파싱 문제와 구분한다.

---

### Mistake 5 — ruff E402 (import 순서)

**무슨 일**: `load_dotenv()`를 import 사이에 넣어서 ruff가 E402를 냈다.
```python
from dotenv import load_dotenv
load_dotenv()            # ← 여기
from fastapi import FastAPI  # E402: module level import not at top of file
```

**다음에 할 것**:
- `load_dotenv()`는 `# noqa: E402` 처리하거나, ruff 설정에서 예외 추가.
- `pyproject.toml`에 미리 추가:
  ```toml
  [tool.ruff.lint.per-file-ignores]
  "src/main.py" = ["E402"]
  ```

---

---

### Mistake 6 — LLM에 full schema 넘겨서 nested children까지 채워짐

**무슨 일**: `generate_list(prompt, brand, PlanStep)` 호출 시 `PlanStep.model_json_schema()`를
tool_use input_schema로 그대로 넘겼다. `PlanStep` 스키마에 `patches: list[PatchProposal]`가 포함되어 있어서
LLM이 "친절하게" patches와 checks까지 전부 채워 반환했다.
결과: POST /plan이 plan + patch + check를 한 번에 다 하는 것처럼 동작.

**왜 발생**: 도메인 모델 schema(저장/응답용)와 LLM input schema(생성 요청용)를 분리하지 않았다.

**다음에 할 것**:
- LLM 호출용 input schema를 별도로 정의한다: `PlanStepInput`, `PatchProposalInput`
- 규칙: **LLM input schema는 LLM이 생성해야 할 필드만 포함. id, created_at, 자식 배열 제외.**
- `generate(prompt, brand, PlanStepInput)` → `PlanStep(**result)` 로 변환
- POST /plan 응답에서 `patches: []` 인지 항상 확인한다.

---

---

### Mistake 7 — guardrails가 AGENTS.md를 실제로 읽지 않음 (case-01-session-second)

**무슨 일**: `guardrails.run_checks(diff)`가 브랜드를 받지 않았고, severity를 코드에 하드코딩했다.
`llm._plan_prompt()`도 AGENTS.md 내용을 LLM에 전달하지 않았다.
`efood/AGENTS.md`를 수정해도 guardrail 동작이 바뀌지 않는 상태였다.

**왜 발생**: Protocol의 Agent B 프롬프트에 "brand parameter is present for future use, **even if unused now**"라고 적혀 있었다.
에이전트가 이 표현을 "브랜드를 받되 쓰지 않아도 된다"로 해석했다.
Phase 5 JD Alignment Check가 체크박스 테이블이라 자동 검증이 없었고, 90분 제약 안에서 눈으로 확인하지 못했다.

**핵심 원인**: "brand parameter accepted but unused" = 구현 누락. 파라미터 시그니처만 있고 파일을 읽지 않으면 요구사항 미충족.

**다음에 할 것**:
- Protocol Agent B 프롬프트에서 "unused" 표현 제거 → `_parse_severities(brand)` 구현 명시
- Phase 5 JD Alignment Check를 체크박스 → 실행 가능한 bash 검증 스크립트로 교체
- 리트머스 테스트: `efood/AGENTS.md`의 R1 severity를 WARN→BLOCK으로 바꾸고 테스트 재실행 → 결과가 바뀌어야 함
- Anti-pattern #7/#11 추가: "guardrail이 AGENTS.md를 읽지 않으면 구현 누락"

---

### Mistake 8 — Idempotency-Key를 endpoint scope 없이 전역 캐시 키로 사용

**무슨 일**: 같은 `Idempotency-Key`를 `POST /sessions/{id}/plan`과
`POST /sessions/{id}/patches`에서 재사용했을 때, patch 생성 라우트가 plan 응답 캐시를 읽었다.
plan 응답은 list이고 patch 응답은 object라서 `PatchProposalOut.model_validate(...)`에서
Pydantic validation error가 발생했다.

**왜 발생**: idempotency cache key를 사용자 제공 header 값만으로 저장했다.
HTTP method, route/path, actor, request body fingerprint 같은 request scope를 포함하지 않아
서로 다른 endpoint의 응답이 같은 캐시 슬롯을 공유했다.

**핵심 원인**: `Idempotency-Key`는 클라이언트가 재시도 단위를 식별하는 값일 뿐,
서버 전역에서 유일한 response cache key가 아니다.

**다음에 할 것**:
- idempotency 저장 키는 최소한 `method + path + Idempotency-Key`로 scope 처리한다.
- 가능하면 `actor + method + route template + request body hash + Idempotency-Key` 조합을 쓴다.
- 같은 `Idempotency-Key`를 서로 다른 endpoint에 재사용하는 회귀 테스트를 추가한다.
- cache hit 시 response schema가 현재 endpoint의 response_model과 맞는지 검증 실패가 나면
  500 대신 cache mismatch로 명확히 처리한다.

---

### Mistake 9 — pytest에서 로컬 `src` 패키지를 못 찾음

**무슨 일**: `uv run pytest tests/test_audit.py -v`가 `ModuleNotFoundError: No module named 'src'`로 collection 단계에서 실패했다.

**왜 발생**: pytest 실행 시 프로젝트 루트가 import path에 명시되지 않아 테스트가 `src.main`을 찾지 못했다.

**핵심 원인**: 단일 케이스 디렉터리를 독립 프로젝트처럼 실행하지만 패키지 설치 설정 없이 `src` 패키지를 직접 import했다.

**다음에 할 것**:
- 새 케이스 프로젝트를 만들 때 `pyproject.toml`에 `pythonpath = ["."]` pytest 설정을 먼저 둔다.
- 가장 작은 회귀 테스트는 `uv run pytest tests/<new_test>.py -v` collection 성공이다.

---

## Agent Prompt 필수 체크리스트 (Phase 3 시작 전)

### Mistake 9 — Pydantic v2 형제 모델 변환을 직접 검증함 (case-03-context)

**무슨 일**: `AuditRecord.model_validate(ToolInvocation(...))`가 500을 냈다.

**왜 발생**: `AuditRecord`가 `ToolInvocation`을 상속해도 Pydantic v2는 형제/부모 모델 인스턴스를 dict처럼 자동 변환하지 않는다.

**핵심 원인**: 저장 모델을 응답 모델로 바꿀 때 명시적인 직렬화 단계를 빠뜨렸다.

**다음에 할 것**: 모델 간 응답 변환은 `AuditRecord.model_validate(item.model_dump())`처럼 `model_dump()`를 거친다. 회귀 테스트나 curl로 `GET /audit`까지 확인한다.

### Mistake 10 — 설계 SPEC가 assignment 원문 필드명을 덮어씀 (case-03-context)

**무슨 일**: `search_prs.limit`, Slack `channel/since`, GDrive `brand/last_modified`, `/tools.brand_requirements`가 구현에서 빠지거나 다른 이름으로 바뀌었다.

**왜 발생**: 구현이 `assignment.md`의 원문 contract보다 `SPEC.md`의 추상 설계 문장과 mock 편의 필드명을 더 따랐다.

**핵심 원인**: 설계 기록이 원문 API contract를 체크리스트로 고정하지 않으면, 좋은 구조를 만들면서도 public schema가 drift된다.

**다음에 할 것**: SPEC 작성 시 assignment 원문 endpoint, args, result field를 그대로 복사한 contract 표를 넣고, route test에서 required args와 반환 필드명을 검증한다.

Agent A (routes + LLM) prompt에 반드시 포함할 것:

```
- from dotenv import load_dotenv; load_dotenv() must be FIRST in main.py, before any local imports
- All LLM calls: use tool_use with tool_choice={"type":"tool","name":"output"}, max_tokens=4096
- Never use json.loads() on raw LLM response text — use response.content[0].input directly
- No print() anywhere — use logging
```

Agent B (guardrails) prompt에 반드시 포함할 것:

```
- No LLM calls in this file — deterministic regex only
- Return one GuardrailCheck per rule always (pass or fail)
- brand parameter must be in the signature even if unused
```

---

## E2E 검증 안전한 패턴

```bash
# 응답을 파일로 받아서 파싱
curl -s -X POST localhost:8000/sessions \
  -H "Content-Type: application/json" \
  -d '{"title":"test","description":"test","brand":"efood"}' \
  -o /tmp/session.json

SESSION=$(python3 -c "import json; print(json.load(open('/tmp/session.json'))['id'])")
```
