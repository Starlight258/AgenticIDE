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

## Agent Prompt 필수 체크리스트 (Phase 3 시작 전)

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
