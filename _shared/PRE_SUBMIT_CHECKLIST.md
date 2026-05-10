# PRE_SUBMIT_CHECKLIST.md — 제출 직전 구두 확인 리스트

> 본게임 4시간 끝나기 전 30분, 또는 take-home 제출 직전에 직접 손으로 돌리는 체크리스트. 한 줄씩 입으로 읽으면서 ✅ 또는 ❌ 표시. **❌ 한 개라도 있으면 제출 전 fix.**
>
> 우선순위가 부족하면: **1 → 3 → 7 → 5** (이 4개 빠지면 22점도 위태로움).

---

## 1. pytest 다 통과 (3분)

```bash
cd <repo>
uv run pytest -v
```

- [ ] 모든 테스트 PASS
- [ ] e2e 테스트가 실제 LLM 안 부르는지 (`get_llm` override 또는 mock 모드)
- [ ] 깨진 거 1개라도 있으면 fix 또는 skip 사유 명시

---

## 2. ruff 통과 (1분)

```bash
uv run ruff check src tests
uv run ruff format --check src tests
```

- [ ] check 깨끗
- [ ] format 깨끗
- [ ] 깨지면 `uv run ruff check --fix src tests` 한 번

---

## 3. mock 모드로 API 호출 — `ANTHROPIC_API_KEY` 비우고 (5분)

```bash
unset ANTHROPIC_API_KEY
uv run fastapi dev src/main.py &
sleep 3
```

- [ ] `curl localhost:8000/health` → `{"status":"ok"}`
- [ ] README 의 curl 5단계 그대로 복붙해서 다 200 OK
- [ ] SESSION_ID, STEP_ID, PATCH_ID 다 jq 로 잘 뽑힘
- [ ] `/check` 결과: 기대한 rule (예: G1-G5 다 fail) 정확히 나옴
- [ ] `/readiness` 결과: 기대한 verdict (예: NOT_READY) + block_count·warn_count 맞음

**FAIL 시**: README 의 curl path 와 `routes.py` 의 `@router.post(...)` decorator path 1글자 단위로 비교.

---

## 4. 실제 LLM 호출 — `ANTHROPIC_API_KEY` 넣고 (5분)

```bash
export ANTHROPIC_API_KEY=sk-ant-...
# 서버 reload 후
```

- [ ] `/plan` 응답 시간이 mock 보다 길어짐 (실제 LLM 호출 증거)
- [ ] plan 의 step description 이 mock 의 hardcoded 문구가 아님
- [ ] `/patch` 도 실제 diff 받음
- [ ] structured logs 에 `llm.plan_created` / `llm.patch_created` 찍힘
- [ ] LLM 응답이 schema 와 안 맞으면 retry → 그래도 실패하면 503 (circuit breaker)

**FAIL 시**: `src/llm.py` 의 `tool_choice`, `max_tokens=4096`, retry 동작 확인.

---

## 5. 에러 케이스 4개 직접 발생 (5분)

| 케이스 | 명령 | 기대 status | 기대 error code |
|---|---|---|---|
| auth 없음 | `curl -X POST localhost:8000/sessions -d '{...}'` (헤더 X) | 403 | — |
| 없는 session | `curl localhost:8000/sessions/$(uuidgen)` | 404 | `session_not_found` |
| 같은 patch 두 번 check | `/check` 한 번 더 호출 | 409 | `checks_already_exist` (body 에 기존 checks 포함) |
| 다른 session 의 patch test-run | session A 의 patch 를 session B 에 test-run | 422 | `patch_not_in_session` |

- [ ] 4개 다 status code 정확
- [ ] error code (json 의 `error` 필드) 가 README 의 Error Model 표와 1:1 일치

---

## 6. Swagger UI 직접 (2분)

```
http://localhost:8000/docs
```

- [ ] 등록된 endpoint 8개 다 보임 (`/health` + 7개)
- [ ] 각 path 가 README 와 같음
- [ ] 각 endpoint 의 response_model 이 schema 와 맞음
- [ ] Swagger 에서 직접 1개 요청 보내봐도 200

---

## 7. README 본인이 5분 정독 (5분)

소리 내서 읽거나 머릿속 천천히.

- [ ] "이 단어 내가 평소에 안 쓰는 단어인데?" 1개라도 발견 → 풀어쓰기
- [ ] 한 문장에 한자어 2개 이상 → 다시 써
- [ ] "이 섹션 빼도 의미 안 변함" → 빼기 (Implementation Signals 같은 거)
- [ ] 결정 3개 (예: Readiness / Concurrency / 409 Conflict) 영어로 1분 안에 본인 입으로 설명 가능?
- [ ] README curl 5단계 path → routes.py 의 `@router` 데코레이터 path 1글자 단위 일치
- [ ] Rule 표 (G1-G5 또는 R1-R5) → `<brand>/AGENTS.md` 의 rule 정의와 1글자 단위 일치
- [ ] Entity 이름 → `src/models.py` 클래스 이름과 일치
- [ ] Severity label (BLOCK/WARN/INFO) → 명세 와 일치

---

## 8. git 상태 깔끔 (3분)

```bash
git status
git log --oneline -10
git diff main..HEAD
```

- [ ] working tree clean
- [ ] commit 메시지에 `[AI]` / `[HAND]` prefix (또는 일관된 prefix)
- [ ] commit 메시지가 의미 있음 (예: `[HAND] add readiness aggregator` ✅, `[AI] fix` ❌)
- [ ] `.venv/`, `.pytest_cache/`, `__pycache__/` 가 `.gitignore` 에 있음
- [ ] dead file (안 쓰는 모듈) 없음 또는 README 에 "scaffolding only" 명시

---

## 9. README mermaid 그려지나 (1분)

GitHub 에 push 한 뒤 브라우저에서 README 확인.

- [ ] ERD diagram 그려짐 (텍스트만 나오면 syntax 오류)
- [ ] state diagram 그려짐
- [ ] 텍스트만 나오면 → mermaid 블록의 첫 줄 (`erDiagram`, `stateDiagram-v2`) 오타 확인

---

## 10. how-to-run 1분 안에 됨? (1분, 시계 재면서)

```bash
git clone <repo>
cd <repo>
time (uv sync && uv run pytest)  # 60초 안에 끝나야
```

- [ ] `uv sync` ~ 첫 pytest 통과 까지 60초 이내
- [ ] 평가자가 같은 경험 받음 (clone → 1분 안 → 동작 확인)

---

## 11. LLM 없이도 동작 README 에 명시 (10초)

- [ ] README 에 "without `ANTHROPIC_API_KEY` → mock" 한 줄 있음
- [ ] 평가자가 key 없이 돌릴 가능성 높음 — 명시 안 하면 평가자가 `.env` 만들다가 시간 낭비

---

## 12. multi-brand 동시 호출 (보너스, 3분)

```bash
# brand=efood 로 session 만들어서 /check → R1-R5 나오는지
# brand=glovo 로 session 만들어서 /check → G1-G5 나오는지
```

- [ ] 두 brand 가 각각 다른 rule set 반환 (분기 동작 증명)
- [ ] 각 brand 의 severity 가 그 brand 의 `AGENTS.md` 정의 따라감

---

## 마지막 — 직접 입으로 답하기 (5분)

면접관 시점에서 다음 질문 받았다고 가정. 영어로 30초 안에 답할 수 있는지.

- [ ] "Why did you choose deterministic regex over LLM-based review?"
- [ ] "What happens if two requests arrive simultaneously for the same patch?"
- [ ] "Why does `POST /check` return 409 on retry instead of 200?"
- [ ] "How would you add a new brand?"
- [ ] "What did the LLM do, and what did you do?"

답 못 하는 게 1개라도 있으면 → 그 부분이 README 에서 "본인 단어로 안 들리는" 곳. 풀어쓰기.

---

## 우선순위 컷 (시간 없을 때)

| 시간 | 무엇 | 점수 영향 |
|---|---|---|
| 30분 | 1 → 2 → 3 → 5 → 7 → 8 | 22+ 보장 |
| 20분 | 1 → 3 → 7 → 5 | 22+ 보장 (위태로움) |
| 10분 | 1 → 7 → 3 (curl 5단계만) | bubble (18~21) |
| 5분 | 1 (pytest) + 7 (README 정독 만) | 18 미만 위험 |

**5분 미만이면 제출 미루고 1시간 더 달라고 정직하게 말하기 — 깨진 결과물 제출보다 나음.**
