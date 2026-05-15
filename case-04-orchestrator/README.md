# README Writing Rules

Rules for writing take-home assignment READMEs. Template is below.

---

## Rules Before You Write

### Remove AI smell

1. **No coined terms**: if you can't defend the word in an interview, don't use it. Use verbs instead. ❌ "deterministic sandwich" → ✅ "the LLM is wrapped on both sides by deterministic code"
2. **No lists longer than 3 items in a sentence**: listing 7 things is an AI pattern. Stop at 3; move the rest to a table or delete if already covered by a diagram.
3. **No hedge language**: replace vague softeners with direct verbs. ❌ "instead of silently pretending a new check was created" → ✅ "instead of returning a fake new check"
4. **Introduce jargon once, then use the abbreviation**: define it on first use, either inline or as a note. After that, use the short form freely. ❌ "checks the stored version before saving; if another request changed it first, returns 409" → ✅ "CAS (Compare-And-Swap) on `version`; if another request changed it first, returns 409", then use "CAS" freely after that. Dropping jargon entirely can make things *more* confusing, not less.
5. **No awkward translations**: write naturally. ❌ "`brand="glovo"` is the evaluated path" → ✅ "currently implemented for `brand="glovo"`"

### Cut duplication

6. **Never repeat what a diagram already shows**: if it's in the diagram, don't restate it in prose below.
7. **No "Implementation Signals" section**: reviewers read the code. Don't list files and say "look here", that is not a README section.
8. **Table rows and subsections must not say the same thing twice**: if a decision is in the Other decisions table, don't also give it a `###` subsection. Pick one.

### Structure

9. **Trust Boundaries: 5-6 rows max**: merge rows that repeat the same idea from different angles. Mock mode and dev tooling are not trust boundaries, leave them out.
10. **Trust Boundaries AI role column: use "None" for everything AI does not control**: don't split into "None" vs "Not involved", that distinction confuses readers. Use "None" uniformly.
11. **No decision numbering**: name headings by what they decide. ❌ "### Decision 2: Readiness" → ✅ "### Readiness, which patch is the merge candidate?"
12. **Significant decisions need an options table**: showing alternatives is what makes it a trade-off. A decision with no alternatives is just a statement.
13. **Options table: options as rows, criteria as columns**: ❌ options as columns (table breaks when you add a third option) → ✅ options as rows with "How it works" and "Risk" as columns. Easier to scan and extend.
14. **How to Run opener is one sentence**: credentials present vs absent, nothing more.
15. **Show Swagger URL explicitly**: don't make the reader guess. Add `http://localhost:PORT/docs` after the run command.
16. **Second line of the title says what it is NOT**: makes scope immediately clear. Use two sentences, not a dash. ❌ "Not a git apply, the safety check between..." → ✅ "Not a git apply or CI runner. The safety check between..."
17. **No `:` after headings**: h2/h3 already signals a section. No `:` mid-sentence either (e.g. "it means:" → "it means one of three things").
18. **No `—` em dash and no `-` hyphen for mid-sentence pauses**: restructure with a period, comma, or parentheses. ❌ "the LLM is wrapped on both sides by deterministic code — it only produces structured output" → ✅ "the LLM is wrapped on both sides by deterministic code. It only produces structured output." Bullet labels and ID-like compounds (e.g. `Compare-And-Swap`) keep the hyphen.

### Tone, Professional / Article-style

Target tone is the Delivery Hero tech blog (e.g. "From Manual Coding to AI Orchestration"), formal-professional and structured. Velocity-first internal-note style is not the target.

19. **Active voice with strong verb subjects**: start sentences with the actor, not "There is" / "It is" / "This is".
    - ❌ "There are three design decisions in this service"
    - ✅ "Three decisions shaped this design"
    - ❌ "It is important to validate input before storage"
    - ✅ "The service validates input before storage"

20. **"We" or omitted subject, never passive voice**: pick one consistent voice and avoid `is/was/are/were + past participle by`.
    - ❌ "Redis was chosen for persistence guarantees"
    - ✅ "We chose Redis for its persistence guarantees"

21. **Logical connectors between sentences**: use Firstly / Furthermore / However / Subsequently / Therefore / Finally to show flow. One connector per paragraph maximum, overuse signals AI text.

22. **Bullets explaining concepts are complete sentences**: telegraphic bullets are for command sequences (How to Run), not for design rationale.
    - ❌ "- Faster reads / - Less memory / - Easier debugging"
    - ✅ "- **Faster reads**: the in-memory lookup avoids a network round trip"

23. **Restrained adjectives**: use `significant`, `competitive`, `careful`, `consistent`, `robust`, `effective`, `comprehensive`. Avoid `amazing`, `great`, `super`, `really`, `very`, `cutting-edge`, `sophisticated`.

24. **Section opener sets up what follows**: one sentence at the top of each major section that frames the rest. Design Decisions opens with "Three decisions shaped this design." Error Model opens with "Errors follow the 404 / 422 / 409 conventions."

25. **No contractions in body prose**: use "do not", "cannot", "will not" in narrative paragraphs. Contractions are acceptable in code comments and inline command examples.

26. **Concrete numbers over vague quantifiers**: replace "many", "several", "a lot of" with actual counts.
    - ❌ "many tests cover this behavior"
    - ✅ "12 tests cover this behavior"

27. **Verbs over abstract nouns**: replace nominalizations (`-tion`, `-ment`, `-ness`) with the underlying verb.
    - ❌ "Implementation of validation is performed before storage"
    - ✅ "The service validates before storing"

### Correctness, check before submitting

28. **Every claim in README must match the actual assignment spec**: before finalizing, open the original assignment email/doc and verify each section against it line by line. README G1-G5 descriptions, entity names, endpoint paths, and severity labels must match what the spec and code actually say, not what you assumed or what a previous draft had. If you did not write the code yourself, read the relevant files before writing about them.
29. **Don't use SQLite as the "If More Time" target**: SQLite is a local convenience choice, not a production direction. Point to MySQL or PostgreSQL via docker-compose instead.
30. **"Bearer demo" belongs in If More Time**: hardcoded tokens are a known gap. Call it out and say what real auth would look like (JWT or API key validation).

### Diagrams

31. **Architecture diagrams must be Excalidraw or Mermaid**: no text diagrams (`->`, `|`, `+--+`). Ask Coco to draw it.
    - Excalidraw: for freeform flow or component layout
    - Mermaid: for flowcharts, sequence diagrams, or state diagrams

---

## Template

### [Case Title]

[One line, what this service does and for whom.] Not a [X]. [What it actually is, in one clause.]

---

#### 1. Problem & Approach

**What this replaces**: [the manual workflow this eliminates, one sentence, start with developer pain]

**API surface**

- `POST /X`, [what it creates]
- `POST /X/{id}/Y`, [what it triggers]
- `GET /X/{id}`, [what it returns]

**Architecture**

[One sentence with verbs. e.g. "the LLM is wrapped on both sides by deterministic code. It only produces structured output, and the service owns everything else."]

[Ask Coco to draw this as a Mermaid flowchart or Excalidraw diagram. Do not write a text diagram.]

**Assumptions**

1. [session/storage scope], [swap path if requirement expands]
2. [brand/tenant scope], [what's implemented now vs extension path]
3. [config source and location], [where it lives and why, especially if non-standard]
4. [LLM output contract], [how output is constrained before storage]
5. [severity semantics], [what BLOCK/WARN means for the downstream gate]
6. [observability], [what trace_id / logging covers now]

---

#### 2. Domain Model

```text
[Entity1] 1—* [Entity2] 1—* [Entity3] 1—* [Entity4]
[Entity1] 1—* [SideEntity]
[ComputedThing] is computed, not stored
```

- `[Entity1]`, [one-line purpose, key fields]
- `[Entity2]`, [one-line purpose]
- `[Entity3]`, [one-line purpose, note if immutable]
- `[Entity4]`, [one-line purpose]
- `[SideEntity]`, [evidence-only, does not override downstream verdict]

**Trust Boundaries** (5-6 rows max, merge similar rows, no mock mode row)

| Boundary | AI role | Deterministic code role |
|---|---|---|
| [core LLM action] | [what LLM produces] | [what service validates/enforces] |
| [second LLM action] | [what LLM produces] | [how output is stored/constrained] |
| [guardrail / policy] | None | [what runs deterministically, how severity is sourced] |
| [readiness / gate] | None | [how verdict is computed, what blocks it] |
| [test evidence / side input] | None | [stored as evidence only, does not override verdict] |
| [HTTP / config / auth] | None | [validation, ownership checks, config re-read, merge into one row] |

---

#### 3. Design Decisions

Three decisions shaped this design. Each involved a non-obvious trade-off.

[Significant decisions get a subsection with an options table.
Name headings by what they decide, not by a number.
Everything else goes in the Other decisions table.
Never list more than 3 items in a sentence, use a table instead.]

##### [Decision name, e.g. "Readiness, which patch is the merge candidate?"]

[One sentence on why this was non-obvious.]

| | How it works | Risk |
|---|---|---|
| Option A: [name] | [one sentence] | [what breaks] |
| Option B: [name] | [one sentence] | [what breaks] |

**Decision, Option [N].** [One or two sentences, the correctness argument. Name the assumption that makes the trade-off acceptable.]

[Any cascading rules or states that follow.]

##### [Second significant decision]

[Same format. Add a column if three options.]

##### Other decisions

| Background | Options | Decision | Reason |
|---|---|---|---|
| [why this needed a decision] | [A vs B] | [chosen] | [one sentence] |
| [why this needed a decision] | [A vs B] | [chosen] | [one sentence] |

---

#### 4. Error Model

Errors follow the 404 / 422 / 409 conventions. Path IDs use 404. Body IDs use 422. Duplicate event creation returns 409 with the existing record in the body.

| Case | Status | Error |
|---|---:|---|
| Missing [resource] path ID | 404 | `[resource]_not_found` |
| [Cross-session ownership violation in path] | 404 | `[resource]_not_found` |
| Body references unknown [resource] | 422 | `[resource]_not_found_in_payload` |
| Body references another session's [resource] | 422 | `[resource]_not_in_session` |
| Duplicate event creation | 409 | `[event]_already_exist` |
| Optimistic lock race | 409 | `version_conflict` |

---

#### 5. AI Usage Log

We used AI as a reasoning partner, not only as a code generator.

Example prompts used during design:

- "[question about failure modes]"
- "[question that challenged my initial approach]"
- "[comparison prompt, A vs B for X]"

Every AI-generated file went through `ruff check`, `uv run pytest`, and a manual diff scan. No AI output was committed without a test covering the specific behavior.

| Part | Verification |
|------|--------------|
| Domain models | Type-checked by Pydantic |
| [File/component] | [how it was verified] |
| README | Cross-checked against route decorators, models, and tests |

---

#### 6. If More Time

Each item below names what the extension enables, not just what it is. Where the extension path already exists in the schema, this section says so explicitly.

- **Real auth**, replace the hardcoded token with JWT or API key validation.
- **MySQL / PostgreSQL**, swap the current DB for a real one via docker-compose, add migrations and indexes.
- **[Feature]**, [one sentence on what it enables].
- **Multi-tenant**, `[field]` already in schema, add `[config file]` per tenant, no route changes needed.
- **Observability**, push `trace_id` spans to [system], ties into [downstream metric].
- **Recompute**, needed when [config source] changes. The current design stores results as immutable audit events.

---

#### How to Run

##### Setup

```bash
uv sync
uv run pytest
uv run fastapi dev src/main.py
```

Swagger UI, http://localhost:PORT/docs

##### Auth

All requests require an `Authorization` header. Any bearer value is accepted. There is no real token validation in local dev.

```bash
-H "Authorization: Bearer <any>"
```

##### LLM

[One sentence, what happens with vs without credentials.]

##### [Workflow name]

```bash
# 1. [create session/workspace]
RESOURCE=$(curl -s -X POST localhost:8000/[endpoint] \
  -H "Content-Type: application/json" \
  -d '[payload]' \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")

# 2. [generate plan/sub-resource]
SUB=$(curl -s -X POST localhost:8000/[endpoint]/$RESOURCE/[sub] \
  | python3 -c "import sys,json; print(json.load(sys.stdin)[0]['id'])")

# 3. [core step, demonstrates the main feature]
curl -s -X POST localhost:8000/[endpoint]/$RESOURCE/[action] \
  | python3 -m json.tool

# 4. [readiness or full state]
curl -s localhost:8000/[endpoint]/$RESOURCE | python3 -m json.tool
```

Expected, [what the output shows and why].
```