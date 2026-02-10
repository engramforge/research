---
model: claude-opus-4.6
backend: anthropic
timestamp: 2026-02-09T10:23:40.146130
cost_usd: 0.4649
tokens: 3568
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["models", "task", "search", "tree", "context", "analysis", "plan", "constraints", "replace", "tests", "change", "output", "T"]
---

# Model Preferences: claude-opus-4.6

**Generated:** 2026-02-09T10:23:40.146130  
**Cost:** $0.4649  
**Tokens:** 3568

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



# Code Generation Preference Profile — Deep Analysis

I've thought carefully about this, focusing on what genuinely produces my best output rather than what sounds theoretically elegant.

---

## 1. Output Format: XML Tags with Markdown Code Blocks Inside

**My strong preference: XML structural tags wrapping markdown code blocks.**

This isn't arbitrary — XML tags give me unambiguous boundaries that prevent me from conflating files, mixing explanation with code, or losing track of where I am in a multi-file response.

```xml
<file path="app/models/order.py" language="python" action="create">
```python
# code here
```
</file>

<file path="app/routers/orders.py" language="python" action="modify">
```python
# code here
```
</file>
```

**Why this works best:**
- The `path` attribute forces me to commit to a file location upfront, which prevents architectural drift mid-response
- The `action` attribute (create/modify/delete) makes my intent explicit
- The `language` attribute primes my generation for the correct syntax
- Markdown code blocks inside give you syntax highlighting in any renderer

**What works poorly for me:** Pure JSON structure. I tend to escape-hell strings and produce malformed output. Plain text with ad-hoc delimiters leads to ambiguity.

---

## 2. Instruction Style: Constraint-Based Core + Example-Driven Patterns

**My best output comes from a specific layered approach:**

```
Layer 1 (MUST have): Hard constraints and non-negotiables
Layer 2 (SHOULD have): Architectural patterns shown by example
Layer 3 (FREE): Implementation details left to my judgment
```

**Here's why, with a concrete example:**

```markdown
## Constraints (these anchor me)
- MUST use dependency injection for auth, not decorators
- MUST NOT put business logic in route handlers
- MUST return RFC 7807 problem details for errors
- MUST use UUID v4 for resource IDs

## Pattern (this shows me your style)
Here's how we built the /users endpoint:
```python
@router.post("/", status_code=201, response_model=UserResponse)
async def create_user(
    payload: UserCreate,
    current_user: User = Depends(require_auth),
    service: UserService = Depends(get_user_service),
):
    return await service.create(payload, created_by=current_user.id)
```

## Goal (this gives me room)
Build the /orders endpoint following the same pattern.
```

**What degrades my output:** Overly detailed step-by-step instructions paradoxically make me worse. I start following the steps mechanically and stop reasoning about correctness. I'll implement exactly what you said even if step 4 contradicts step 7.

---

## 3. Context Presentation: File Tree + Key Excerpts + I Ask

**The optimal approach is a three-part context block:**

```xml
<context>
<tree>
app/
├── main.py              # FastAPI app factory
├── dependencies.py      # Auth, DB session deps
├── models/
│   ├── __init__.py
│   ├── user.py          # User SQLAlchemy + Pydantic models
│   └── order.py         # ← TO CREATE
├── routers/
│   ├── __init__.py
│   ├── users.py         # Existing CRUD reference
│   └── orders.py        # ← TO CREATE
├── services/
│   └── order_service.py # ← TO CREATE
└── tests/
    └── test_orders.py   # ← TO CREATE
</tree>

<excerpt path="app/dependencies.py">
```python
async def require_auth(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    # ... validates JWT, returns User or raises 401
```
</excerpt>

<excerpt path="app/models/user.py">
```python
class UserResponse(BaseModel):
    id: UUID
    email: str
    model_config = ConfigDict(from_attributes=True)
```
</excerpt>
</context>
```

**Why this specific structure:**
- The **tree** gives me the architectural map — I know where things go and what already exists
- The **excerpts** of interfaces I need to integrate with (deps, existing models) prevent me from inventing incompatible signatures
- Marking files **TO CREATE** vs existing tells me what I'm building vs what I'm consuming
- I don't need full file contents of things I'm not modifying — they add noise and consume context window

**Critical insight:** The #1 cause of bad code generation from me is **missing interface context**. If I don't see the actual signature of `require_auth`, I'll guess — and I'll guess wrong 30% of the time. Show me the boundaries I need to connect to.

---

## 4. Diff Generation: Full File for New, Surgical Blocks for Modifications

**My honest assessment: I'm unreliable at generating syntactically correct unified diffs.** I miscalculate line numbers, get context lines wrong, and produce diffs that won't apply cleanly. This is a known weakness.

**What I recommend instead:**

For **new files** — full file content, always:
```xml
<file path="app/models/order.py" action="create">
```python
# Complete file content
```
</file>
```

For **modifications** — a search/replace block format:
```xml
<file path="app/routers/__init__.py" action="modify">
<change>
<search>
from .users import router as users_router

def register_routes(app: FastAPI):
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
</search>
<replace>
from .users import router as users_router
from .orders import router as orders_router

def register_routes(app: FastAPI):
    app.include_router(users_router, prefix="/api/v1/users", tags=["users"])
    app.include_router(orders_router, prefix="/api/v1/orders", tags=["orders"])
</replace>
</change>
</file>
```

**Why search/replace beats diffs:** The search block is an exact string match — no line numbers to miscalculate. It's unambiguous, it's verifiable, and it applies cleanly. If the search block doesn't match, you know immediately something is wrong.

---

## 5. Special Syntax and Markers

### Markers that genuinely help me:

**a) Thinking separation:**
```xml
<analysis>
Before I write code, let me work through the design decisions...
- Order total: compute on creation or store? Store — avoids recalculation and captures point-in-time pricing.
- Status field: enum. Start with PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED.
- Should OrderItem be a separate DB table? Yes — 1:N relationship.
</analysis>
```
When I'm given space (or take space) to reason before coding, the code quality jumps significantly. Without this, I sometimes start writing and paint myself into corners.

**b) Multi-file ordering:**
```xml
<plan>
1. app/models/order.py — Domain models (no dependencies on other new files)
2. app/services/order_service.py — Business logic (depends on models)
3. app/routers/orders.py — HTTP layer (depends on service + models)
4. app/routers/__init__.py — Registration (modify existing)
5. tests/test_orders.py — Tests (depends on everything)
</plan>
```
Explicitly planning file order prevents me from forward-referencing things I haven't defined yet.

**c) Requirement traceability tags:**
```python
# [REQ: auth-required]
current_user: User = Depends(require_auth),

# [REQ: validate-non-empty-items]
@field_validator("items")
def items_must_not_be_empty(cls, v):
    if not v:
        raise ValueError("Order must contain at least one item")
    return v
```
When you ask me to trace requirements, I'm more thorough about covering them all.

---

## 6. Quality Optimization — What Actually Moves the Needle

### Security
**What helps most: Threat-specific constraints.**

```markdown
## Security Requirements
- SQL injection: Use parameterized queries only (SQLAlchemy ORM, no raw SQL)
- IDOR: Verify order.owner_id == current_user.id before returning
- Mass assignment: Use explicit Pydantic models, never pass **request.dict() to ORM
- Rate limiting: Note where to add, don't implement (separate concern)
```

Generic "make it secure" produces generic output. Specific threat models produce specific defenses.

### Test Coverage
**What helps most: Telling me the test categories you expect.**

```markdown
## Required Test Categories
- Happy path (valid input → expected output)
- Validation boundaries (quantity=0, quantity=-1, quantity=1)
- Auth failures (missing token, expired token, wrong role)
- Edge cases (single item, max items, unicode in notes)
- Idempotency considerations
```

Without this, I default to happy-path + one negative test. With explicit categories, I'm thorough.

### Architecture
**What helps most: Naming the pattern.**

Say "use the Service Layer pattern" or "follow Hexagonal Architecture" or "keep it simple — logic in handlers is fine for this." When I know the target architecture, I'm consistent. When I'm guessing, I oscillate between over-engineering and under-engineering within the same response.

### Maintainability
**What helps most: Showing me your existing code.**

I will match your style, naming conventions, error handling patterns, and project structure if you show me examples. This is more effective than any style guide description. One real file from your codebase teaches me more than ten paragraphs of preferences.

---

## 7. Framework-Specific Preferences

### Python / FastAPI

This is where I produce my **strongest output**. Specific things that help:

```markdown
- Python version: 3.11+ (so I can use modern syntax)
- Async or sync: async (I'll use async def, AsyncSession, etc.)
- Pydantic version: v2 (model_config = ConfigDict, not class Config)
- ORM: SQLAlchemy 2.0 style (select() not query())
- Testing: pytest + httpx.AsyncClient (not TestClient)
```

**Common mistake I make without guidance:** Mixing Pydantic v1 and v2 syntax. Explicitly stating the version prevents this.

### C# / ASP.NET Core

I'm strong here but need version anchoring:

```markdown
- .NET version: 8 (so I use primary constructors, minimal APIs if desired)
- Approach: Controller-based or Minimal API?
- DI pattern: Constructor injection
- Validation: FluentValidation or DataAnnotations?
- ORM: EF Core with repository pattern or direct DbContext?
```

**My specific weakness:** I sometimes generate .NET 6 patterns when you want .NET 8, or vice versa. The version matters enormously for C# because the idioms shift significantly between versions.

### Java / Spring Boot

I'm competent but this is where I benefit most from pattern examples:

```markdown
- Java version: 21 (records, pattern matching, virtual threads?)
- Spring Boot version: 3.2+
- Validation: Jakarta Bean Validation
- Response pattern: ResponseEntity<T> or direct return with @ResponseStatus?
- Exception handling: @ControllerAdvice with ProblemDetail?
- Lombok: Yes/No? (This changes every file significantly)
```

**My specific weakness in Java:** Verbosity management. Without guidance, I either over-use Lombok (which some teams hate) or write extremely verbose code (which obscures intent). Tell me your Lombok policy.

### Cross-Framework Insight

When generating the **same endpoint across all three frameworks**, it helps enormously to say:

```markdown
Generate in this order: Python first, then C#, then Java.
```

Python/FastAPI is the most concise, so I establish the logic cleanly. Then I translate to C# and Java with the logic already solid. If I start with Java, I sometimes get lost in boilerplate and introduce logic errors that propagate.

---

## Putting It All Together — Optimal Prompt Template

Here's the prompt structure that would produce my best work for the example task you provided:

```xml
<task>
Add POST /api/v1/orders endpoint with Pydantic validation and auth dependency.
</task>

<constraints>
- MUST use Pydantic v2 with ConfigDict
- MUST use async/await throughout
- MUST separate HTTP layer (router) from business logic (service)
- MUST NOT put calculation logic in the route handler
- MUST return 201 with Location header on success
- MUST use Depends(require_auth) for authentication
</constraints>

<context>
<tree>
<!-- file tree here -->
</tree>
<excerpt path="app/dependencies.py">
<!-- auth dependency signature -->
</excerpt>
</context>

<models>
- OrderItem: product_id (str), quantity (int, gt=0), unit_price (float, gt=0)
- OrderCreate: items (list[OrderItem], min_length=1), notes (str | None = None)
- OrderResponse: id (UUID), items, total_amount (float), created_at (datetime), status (str)
</models>

<tests>
Required test cases:
- Valid order with multiple items → 201, correct total
- Empty items list → 422
- Quantity = 0 → 422
- Negative unit_price → 422
- No auth token → 401
- Single item order → 201, total = quantity * unit_price
</tests>

<output>
Use XML file tags with markdown code blocks.
Show files in dependency order.
Use search/replace for modifications to existing files.
</output>
```

---

## Final Honest Notes

1. **Context window management matters.** If you dump 15 full files into context, my quality on the actual task degrades. Give me the interfaces, not the implementations, of things I'm consuming.

2. **I'm better at generating new code than modifying existing code.** For modifications, the search/replace format keeps me honest. For new code, let me write complete files.

3. **Corrective feedback is extremely valuable.** If I generate something and you say "this is wrong because X," my second attempt is dramatically better than my first. Don't hesitate to reject and redirect.

4. **I will match the quality of the prompt.** A precise, well-structured prompt with clear constraints gets precise, well-structured code. A vague prompt gets my best guess, which is often not your best option.

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "models",
    "task",
    "search",
    "tree",
    "context",
    "analysis",
    "plan",
    "constraints",
    "replace",
    "tests",
    "change",
    "output",
    "T"
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
python run_benchmark.py --model claude-opus-4.6 --use-model-preferences
```
