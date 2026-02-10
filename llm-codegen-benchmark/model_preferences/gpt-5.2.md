---
model: gpt-5.2
backend: openai
timestamp: 2026-02-09T10:26:37.390925
cost_usd: 0.0327
tokens: 1955
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["TEntryPoint", "thinking"]
---

# Model Preferences: gpt-5.2

**Generated:** 2026-02-09T10:26:37.390925  
**Cost:** $0.0327  
**Tokens:** 1955

## Meta-Prompt Used

```
You are about to help generate code for enterprise applications across multiple frameworks:
- Python with FastAPI (REST APIs)
- C# with ASP.NET Core (Web APIs)
- Java with Spring Boot (REST Controllers)

Before we begin actual code generation tasks, I want to understand YOUR preferences for optimal output quality.

Please analyze how you work best and provide guidance on the following aspects:

## 1. Output Format
What format do you prefer for delivering code changes?
- XML tags (e.g., <code>, <...
[Full prompt truncated for brevity]
```

## Model Response

## 1. Output Format (what yields best results)

### Preferred default: **Markdown code blocks with file paths + (optional) unified diff**
- **Why it works well:** It’s human-readable, easy to copy/paste, and supports multi-file changes cleanly.
- **Best practice structure:**
  1. Short “Plan / Summary”
  2. File-by-file code blocks labeled with paths
  3. Notes on migrations/config/env if needed
  4. Tests

**Example (multi-file):**
```text
# Files changed
- app/api/v1/orders.py
- app/schemas/orders.py
- tests/test_orders.py
```

```python
# app/schemas/orders.py
...
```

### When I prefer **unified diff (git-style)**
- When you’re applying changes via tooling/patches or want minimal deltas.
- Especially good for small edits to existing files.

### Formats I can use but are less optimal
- **JSON structure:** good for machine consumption, but awkward for large code blocks and multi-language formatting.
- **XML tags:** workable, but tends to add noise and doesn’t help correctness.
- **Plain text delimiters:** okay, but easier to misapply than file-path markdown.

**If you want one “best overall” standard:**  
**Markdown with file paths** for new/changed files, and **unified diff** when patch-application matters.

---

## 2. Instruction Style (what produces highest-quality code)

### Best: **Mix of constraint-based + example-driven + a bit of high-level goal**
What helps most is:
1. **High-level goal** (what feature does)
2. **Constraints** (must/must not; security; performance; compatibility)
3. **Examples** (request/response samples, existing patterns, preferred libraries)
4. **Acceptance criteria** (tests, status codes, edge cases)

**Why:** Constraints prevent wrong assumptions; examples align style; acceptance criteria drives completeness.

### Step-by-step instructions
- Helpful when you have a very specific approach (e.g., “use repository pattern, don’t touch controllers”).
- But overly prescriptive steps can conflict with existing architecture; I do best when steps are *intent-focused* rather than *implementation-micromanaged*.

---

## 3. Context Presentation (how to give me existing code)

### Best default: **File tree + key excerpts + “tell me what not to change”**
Provide:
- A **file tree** (or module list)
- The **relevant files in full** (controllers/routes, schemas/DTOs, auth, DB layer, test setup)
- Any **existing conventions** (error format, logging, dependency injection, naming)

### When full file contents are necessary
- Anything I must modify safely (routing registration, DI container, middleware, security config, test fixtures).
- If you only provide snippets, I may accidentally duplicate patterns or miss existing helpers.

### Good workflow if context is large
- Start with tree + pointers.
- I’ll ask for the exact files I need (fastest path to correctness).

---

## 4. Diff Generation (how to show modifications)

### Preferred: **Either**
- **Unified diff** for edits to existing files, or
- **Full file replacement** for new files / heavily refactored files

**Why:**  
- Unified diff is precise for incremental changes.  
- Full replacement avoids patch conflicts when many lines change.

### What I avoid unless requested
- Side-by-side before/after (verbose, harder to apply)
- Inline comments showing changes (can pollute code)

---

## 5. Special Syntax / Markers (to reduce ambiguity)

### Helpful markers
Use clear sections:

**`## Task`**  
**`## Requirements (must/must not)`**  
**`## Existing behavior / constraints`**  
**`## Files / context`**  
**`## Acceptance tests`**

### For multi-file context
- Label code blocks with **exact paths**.
- If you paste multiple files, separate them with a strong delimiter, e.g.
  - `--- FILE: path/to/file.py ---`

### Distinguishing instructions vs context
- Put instructions in plain text.
- Put code context in fenced code blocks with language tags.

### “Thinking process”
- I don’t need `<thinking>` tags. If you want reasoning, ask for “brief rationale per change” and I’ll provide it without exposing internal chain-of-thought.

---

## 6. Quality Optimization (security, tests, architecture, maintainability)

### Security guidance that materially improves output
- **AuthN/AuthZ requirements:** who can call it, what claims/roles/scopes are required.
- **Threat model constraints:** rate limiting, idempotency, replay protection, input size limits.
- **Data handling rules:** PII fields, logging redaction, encryption at rest/in transit assumptions.
- **Validation rules:** explicit bounds (max list size, max string length), numeric constraints, allowed enums.
- **Error handling contract:** consistent error schema; avoid leaking internals.

### Test coverage guidance that helps most
- Tell me your **test framework** and patterns:
  - FastAPI: `pytest`, `httpx.AsyncClient`, dependency overrides
  - ASP.NET: `xUnit`, `WebApplicationFactory`, TestServer
  - Spring: `@WebMvcTest` vs `@SpringBootTest`, MockMvc, Testcontainers
- Provide **fixtures** and how auth is mocked.
- Define **acceptance tests** as you did (valid/invalid/unauthenticated).

### Architecture/maintainability guidance
- Preferred layering: controller → service → repository (or minimal).
- Transaction boundaries and DB access style.
- Naming conventions and folder structure.
- Observability requirements: structured logging, correlation IDs, metrics.

---

## 7. Framework-Specific Preferences

### Python + FastAPI
**Preferences**
- Pydantic v2 vs v1: tell me which; it changes validators and config.
- Use `APIRouter`, dependency injection via `Depends`.
- Prefer explicit response models and status codes.
- Tests: `pytest` + `httpx` + dependency overrides for auth.

**Common pitfalls I avoid with good context**
- Duplicating routers or missing router inclusion in `main.py`.
- Incorrect auth dependency shape (e.g., expecting `request.state.user` vs `Depends(get_current_user)`).

### C# + ASP.NET Core
**Preferences**
- Minimal APIs vs Controllers: specify which.
- Use DTOs with `DataAnnotations` or FluentValidation—tell me your standard.
- Auth: specify JWT bearer, policies, roles/claims.
- Tests: `WebApplicationFactory<TEntryPoint>` integration tests are usually highest value.

**What I need to know**
- .NET version, nullable reference types, existing DI registrations, mapping (AutoMapper?).

### Java + Spring Boot
**Preferences**
- Controllers with `@RestController`, validation with `jakarta.validation` (`@Valid`, `@NotNull`, etc.).
- Service layer for business logic; repository layer for persistence.
- Auth: Spring Security configuration style (component-based vs older `WebSecurityConfigurerAdapter`).
- Tests: MockMvc for controller tests; Testcontainers for DB integration if needed.

**What I need to know**
- Spring Boot version (2 vs 3 affects `javax` vs `jakarta`), build tool (Maven/Gradle).

### Backend APIs vs frontend
- For backend APIs, I optimize for correctness, validation, security, and tests.
- For frontend, I’d want design system constraints, state management choice, and lint/format rules. (But your focus here is backend.)

### New code vs modifying existing code
- **New code:** I can move fast with conventions + requirements.
- **Modifying existing code:** I strongly prefer seeing the relevant existing files to match patterns and avoid breaking changes.

---

## Applying this to your example task (FastAPI orders endpoint)

To produce the best output, I’d want:
- Existing auth dependency signature (e.g., `get_current_user`) and how to override it in tests.
- Where routers are registered (`main.py` or `app/api/__init__.py`).
- Existing project structure for schemas/models/services.
- Whether persistence is in-memory, SQLAlchemy, or external service.
- Pydantic version and datetime handling conventions (timezone-aware?).

And I’d return:
- `app/schemas/orders.py` (Pydantic models)
- `app/api/v1/orders.py` (router + endpoint)
- Possibly `app/services/orders.py` (total calculation + creation)
- `tests/test_orders.py` (valid/invalid/auth cases)
- In Markdown with file paths (or unified diff if you prefer patching)

---

## If you want a single “preference profile” to use going forward

1. **Provide:** requirements (must/must not) + file tree + relevant files (auth, routing, tests).  
2. **I output:** Markdown with file paths; unified diff on request.  
3. **I include:** brief rationale + edge cases + tests matching your framework.  
4. **You specify upfront:** framework version, validation library choice, auth mechanism, test harness.

If you tell me which of these you want as your house standard (Markdown vs diff; full files vs patches), I’ll stick to it consistently.

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "TEntryPoint",
    "thinking"
  ],
  "quality_tips": [],
  "framework_specific": {}
}
```

## Notes

This preference profile was auto-generated by asking the model about its own preferences.
It may be updated over time as we learn more about optimal prompting strategies.

To use these preferences in a benchmark run:
```bash
python run_benchmark.py --model gpt-5.2 --use-model-preferences
```
