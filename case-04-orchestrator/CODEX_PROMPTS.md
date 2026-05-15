# CODEX_PROMPTS — case-04-orchestrator

실행 순서: #0 직접 실행 → #1과 #2 동시 (각자 worktree) → #3 머지 후 → #4 마지막

---

### Prompt #0 — Worktree Setup (직접 bash에서 실행)

```bash
cd /Users/mae/Desktop/Develop/AgenticIDE/case-04-orchestrator
git worktree add ../wt-routes -b feat/routes-dispatch
git worktree add ../wt-guardrails -b feat/guardrails
git worktree list
```

> 참고: wt-routes와 wt-guardrails는 같은 repo의 다른 폴더다. 두 Codex 세션이 동시에 돌아도 파일 충돌이 없다. worktree list로 경로 확인 후 각 Codex 세션에 경로를 명시한다.

---

### Prompt #1 — Agent A: Models + Routes + Store (wt-routes에서 실행)

```
Branch: feat/routes-dispatch. Worktree: ../wt-routes.
Read SPEC.md §0 (API contract), §도메인 모델, §동시성 분석, §결정 1, §결정 2, §결정 3, §결정 5.
Create:
  src/models.py   — Job, Task, AgentResult, GuardrailCheck 도메인 모델
  src/schemas.py  — JobCreate, TaskOut, DispatchOut, PROut 응답 DTOs
  src/store.py    — in-memory dict[str, Job] + threading.Lock (SPEC §동시성 분석)
  src/routes.py   — SPEC §0의 5개 엔드포인트 (dispatch는 Lock + status 체크 + worktree 생성만)
  src/main.py     — load_dotenv() 첫 줄, FastAPI app, /health
Done: uvicorn src.main:app starts, GET /health → {"status": "ok"}.
Stop before commit. Show diff + 3 commit message options. Wait for my confirm.
```

> 참고: dispatch 엔드포인트는 이번 단계에서 threading.Lock으로 409 체크 + worktree 생성 + task 반환까지만 구현한다. subprocess 실행과 가드레일 연결은 Prompt #3에서 한다. Lock은 status check + update만 감싸야 한다. 에이전트 실행까지 Lock 안에 넣으면 병렬성이 사라진다 (SPEC §동시성 분석 참조).

---

### Prompt #2 — Agent B: Guardrails + Tests (wt-guardrails에서 실행)

```
Branch: feat/guardrails. Worktree: ../wt-guardrails.
Read SPEC.md §0 (GuardrailCheck fields), §결정 3, §5 Design Principles.
Read AGENTS.md — 규칙 목록과 severity 기준이 여기 있다.
Create:
  src/guardrails.py — run_checks(diff, brand) → list[GuardrailCheck]
    _parse_severities(brand): {brand}/AGENTS.md를 실제로 읽어서 severity 결정
    R1~R5 regex 기반, LLM 호출 없음
  tests/test_guardrails.py — R4 BLOCK, R5 BLOCK, clean pass, AGENTS.md drives severity
Done: uv run pytest tests/test_guardrails.py -v 전부 통과.
Stop before commit. Show diff + 3 commit message options. Wait for my confirm.
```

> 참고: _parse_severities는 AGENTS.md를 실제로 읽어야 한다. brand 파라미터만 받고 파일을 안 읽으면 구현 누락이다 (LESSONS_LEARNED Mistake 7). 리트머스 테스트: AGENTS.md R1 severity를 WARN→BLOCK으로 바꾸고 테스트 재실행 시 결과가 바뀌어야 한다.

---

### Prompt #3 — Wire Integration (두 브랜치 머지 후)

```
main에서 두 브랜치 머지:
  git merge feat/routes-dispatch
  git merge feat/guardrails
Wire dispatch logic per SPEC.md §결정 1, §결정 2, §결정 3, §동시성 분석:
  threading.Lock으로 status check + update atomic 처리 (Lock 밖에서 에이전트 실행)
  ThreadPoolExecutor로 task마다 subprocess claude -p 병렬 실행
  각 완료 후 git diff로 변경사항 수거
  run_checks(diff, brand) 자동 실행 → task status 결정
Wire PR endpoint per SPEC.md §결정 5:
  gh pr create 실행, 완료 후 git worktree remove
E2E smoke test (파일로 받아서 파싱 — LESSONS Mistake 4):
  1. POST /jobs → /tmp/job.json
  2. POST /jobs/{id}/dispatch → /tmp/dispatch.json
  3. GET /jobs/{id} 폴링 → status 확인
Done: uv run pytest 전부 통과, uvicorn 시작, smoke test curl 성공.
Stop before commit. Show diff + 3 commit message options. Wait for my confirm.
```

> 참고: subprocess.run은 blocking이라 asyncio loop에서 직접 쓰면 전체 서버가 멈춘다. loop.run_in_executor로 thread pool에 위임해야 한다 (SPEC §결정 2). merge 직후 src/main.py에 load_dotenv()가 있는지 확인한다 (LESSONS Mistake 1).

---

### Prompt #4 — JD Alignment + Requirements Gate + README

```
JD signal 검증 (SPEC.md §JD Signal Map 전 항목):
  grep -En "worktree" src/routes.py
  grep -En "AGENTS\.md|_parse_severities" src/guardrails.py
  grep -En "ThreadPoolExecutor|run_in_executor" src/routes.py
  grep -En "trace_id" src/models.py
  grep -En "tool_choice" src/ -r  (없어야 정상 — claude -p 쓰므로)
  git log --oneline --graph | head -20  (feat/routes, feat/guardrails 브랜치 보여야 함)
SPEC §0 계약 검증: 5개 엔드포인트 응답 필드가 contract와 일치하는지 확인
README 업데이트: README.md 템플릿 규칙에 따라 5개 섹션 작성
Done: pytest green, ruff check src/ clean, README가 SPEC §0과 일치.
Stop before commit. Show diff + 3 commit message options. Wait for my confirm.
```

> 참고: README.md에 이미 작성 규칙이 있다 (em dash 금지, options table 행/열 방향, Mermaid 필수). SPEC §아키텍처의 Mermaid 다이어그램을 README §1에 그대로 옮긴다. README에서 "deterministic sandwich" 같은 coined term은 쓰지 않는다.
