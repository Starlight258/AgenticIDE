# CODEX_PROMPTS.md — case-02-session

## 현재 상태 (2026-05-10)

이미 완료: models, schemas, errors, exceptions, repository 프로토콜, deps, main, glovo/ 파일
베이스라인: `uv run pytest tests/test_guardrails.py` → 9 passed

남은 작업: Prompt #1 (routes+LLM) → Prompt #2 (guardrails+tests) → Prompt #3 (wire) → Prompt #4 (gate+README)
#1과 #2는 워크트리에서 동시 실행 가능.

---

## 워크트리 설정 (bash에서 직접 실행)

```bash
git worktree add ../wt-routes -b feat/case02-routes-llm
git worktree add ../wt-guardrails -b feat/case02-guardrails-tests
```

---

## Prompt #1 — 새 엔드포인트 + MockLLM

> **참고**: readiness 로직이 가장 헷갈리는 부분. "가장 최근 *체크된* 패치 기준"이 아니라 "가장 최근 패치 기준" — SPEC.md §결정 2에 함정 시나리오까지 설명돼있음. 그리고 POST /check는 두 번째 호출 시 200이 아니라 409 반환 (§결정 8).

```
Branch feat/case02-routes-llm, working dir case-02-session/
SPEC.md 전체 읽고 구현.

추가할 것:
- POST /sessions/{id}/plan/{stepId}/patches
- GET  /sessions/{id}/plan/{stepId}/readiness  (§결정 2)
- POST /sessions/{id}/test-runs               (§결정 5, 9)
- POST /check 동작 변경: 409 + CAS           (§결정 7, 8)
- MockLLM auto-fallback, glovo/sample_diff.patch 반환 (§결정 10)

완료 기준: ruff clean + router.routes 8개 이상
stop before commit
```

---

## Prompt #2 — G1-G5 + 테스트

> **참고**: 심각도를 코드에 하드코딩하면 안 됨 — glovo/AGENTS.md를 런타임에 읽어서 결정해야 JD signal ("AGENTS.md") 충족. `test_glovo_agents_md_drives_severity` 테스트가 이걸 검증함. sample_diff.patch는 G1~G5 전부 fail 나오도록 설계돼있어.

```
Branch feat/case02-guardrails-tests, working dir case-02-session/
SPEC.md §결정 6 + glovo/AGENTS.md 읽고 구현.

추가할 것:
- guardrails.py: glovo 브랜드 G1-G5 (기존 R1-R5 유지)
- test_guardrails.py: G1-G5 테스트 + test_glovo_sample_diff_all_five_fail + test_glovo_agents_md_drives_severity
- test_e2e.py: glovo 세션으로 check-twice-409, readiness, test-run, invalid-patch-422 시나리오

완료 기준: pytest tests/test_guardrails.py 전부 pass
stop before commit
```

---

## Prompt #3 — 통합 + Smoke

> **참고**: API key 없이 실행하면 MockLLM이 sample_diff.patch를 반환해서 G1-G5 전부 fail이 자동으로 나옴. smoke test의 핵심 시나리오: check 두 번 → 두 번째 409 확인.

```
두 워크트리 merge 후, working dir case-02-session/

1. uv run pytest -v  (0 failed 확인, skip 금지)
2. uvicorn 실행 후 smoke:
   - POST /sessions (brand=glovo)
   - POST /plan → POST /plan/{stepId}/patches → POST /check → 200 + 5개 fail
   - 같은 patch에 POST /check 다시 → 409 확인
   - GET /readiness → latest_patch_id not null 확인

stop before commit
```

---

## Prompt #4 — 검증 + README

> **참고**: README는 평가자가 코드 안 봐도 설계 의도를 이해할 수 있게 써야 함. 특히 결정 2 (readiness 왜 이렇게?), 결정 7 (낙관적 락 왜?), 결정 8 (409 왜?)는 한 문장씩이라도 근거가 있어야 함.

```
working dir case-02-session/

1. JD signal 체크:
   - guardrails.py가 AGENTS.md를 런타임에 읽는지 확인
   - version 필드 + update_patch_if_version 사용 확인
   - llm.py에 tool_choice 있는지, json.loads 없는지 확인
   - PlanStepOut에 patches 없는지, PatchProposalOut에 checks 없는지 확인

2. README.md 작성 (SPEC.md 기반):
   - Problem & Approach (deterministic sandwich, assumption 6개)
   - Domain Model (관계도, trust boundary 표)
   - AI Leverage 표
   - Trade-offs (§결정 2, 7, 8 근거)
   - If More Time (SQLite, OTEL, multi-brand, LLM-as-judge)
   - How to Run (.env 불필요, MockLLM 자동 동작)

stop before commit
```
