---
model: claude-sonnet-4.5
backend: anthropic
timestamp: 2026-02-06T23:52:05.956031
cost_usd: 0.0453
tokens: 2477
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["security_considerations", "thinking", "analysis", "structure", "migration_steps", "context", "task", "pattern", "constraints", "goal", "framework", "quality", "tests"]
---

# Model Preferences: claude-sonnet-4.5

**Generated:** 2026-02-06T23:52:05.956031  
**Cost:** $0.0453  
**Tokens:** 2477

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

# Code Generation Preferences Analysis

Based on my architecture and how I process information most effectively, here's my detailed analysis:

## 1. Output Format

**Preferred: XML-style tags with Markdown code blocks**

```xml
<analysis>
Reasoning about the task
</analysis>

<file path="src/api/users.py">
```python
# Code here
```
</file>

<tests path="tests/test_users.py">
```python
# Test code here
```
</tests>
```

**Why this works best:**
- XML tags provide clear structural boundaries that help me organize multi-file outputs
- Markdown code blocks preserve syntax highlighting and readability for humans
- Path attributes make file destinations explicit
- Separate thinking/analysis sections prevent contamination between planning and implementation

**Alternative for simple single-file changes:** Plain markdown with clear headers is fine.

## 2. Instruction Style

**Preferred: Hybrid approach with this structure:**

1. **High-level goal** (the "what" and "why")
2. **Specific constraints** (must/must not requirements)
3. **Key patterns or examples** (for complex/novel scenarios)
4. **Freedom in implementation details** (let me choose variable names, exact structure)

**Example of effective instruction:**
```
Goal: Add user authentication endpoint with JWT tokens

Constraints:
- MUST use bcrypt for password hashing
- MUST NOT store tokens in database
- Token expiry: 24 hours
- Follow existing error handling patterns

Reference: Similar to existing /api/login pattern in auth.py

Implementation details: your discretion
```

**Why:** This gives me enough structure to meet requirements while allowing optimization based on context and best practices.

## 3. Context Presentation

**Preferred: Tiered context approach**

**Tier 1 - Always provide:**
- File tree structure showing relevant directories
- Full content of files being modified
- Signatures/interfaces of dependencies

**Tier 2 - Provide selectively:**
- Related files that establish patterns
- Configuration files (requirements.txt, pom.xml, etc.)
- Relevant documentation

**Tier 3 - Reference only:**
- Large unchanged files
- Standard library usage

**Example structure:**
```
Project structure:
src/
├── api/
│   ├── users.py (modifying this)
│   └── auth.py (reference pattern)
├── models/
│   └── user.py (full content needed)
└── database.py (signature only)

File: src/api/users.py
[full content]

File: src/models/user.py
[full content]

Pattern reference from auth.py:
- Uses @router.post() decorator
- Returns JSONResponse with 201 status
- Validates with Pydantic models
```

**Why:** I need complete context for files I'm modifying, but too much irrelevant context can dilute attention. Explicit pattern references help maintain consistency.

## 4. Diff Generation

**Preferred: Context-dependent**

**For small changes (< 20 lines):** Unified diff format
```diff
--- a/src/api/users.py
+++ b/src/api/users.py
@@ -15,6 +15,8 @@
 def get_user(user_id: int):
+    if user_id < 0:
+        raise ValueError("Invalid user ID")
     return db.query(User).filter(User.id == user_id).first()
```

**For moderate changes or new files:** Full file with change markers
```python
# src/api/users.py

# EXISTING CODE (unchanged)
from fastapi import APIRouter
router = APIRouter()

# ADDED: New import for validation
from pydantic import validator

# MODIFIED: Added validation logic
@router.get("/users/{user_id}")
async def get_user(user_id: int):
    # ADDED: Input validation
    if user_id < 0:
        raise HTTPException(status_code=400, detail="Invalid user ID")
    
    # EXISTING CODE
    return db.query(User).filter(User.id == user_id).first()
```

**For major refactoring:** Full file replacement with explanation

**Why:** Diffs are precise but hard to read for large changes. Full files with markers provide context. Let the magnitude of change dictate format.

## 5. Special Syntax and Markers

**Helpful markers I naturally use:**

```xml
<thinking>
For exploratory analysis, trade-offs, planning
Helps me "show my work" without mixing it into code
</thinking>

<file path="exact/path/to/file.ext">
Clear file boundaries for multi-file output
</file>

<tests>
Separate test code from implementation
</tests>

<security_considerations>
Explicit security analysis section
</security_considerations>

<migration_steps>
For database or deployment changes
</migration_steps>
```

**Instruction markers that help me:**
```
CONTEXT: (existing code, system state)
REQUIREMENT: (what must be true)
CONSTRAINT: (what must not be violated)
TASK: (specific action to take)
ANTI-PATTERN: (what to avoid)
```

**Why:** Semantic tags activate different processing modes. `<thinking>` lets me reason without committing to output. Clear input markers reduce ambiguity.

## 6. Quality Optimization

**Security:**
- Explicitly ask: "Consider security implications"
- Mention threat model (e.g., "API will be public-facing")
- Request: "Include input validation and sanitization"
- Specify: Authentication/authorization requirements upfront

**Test Coverage:**
- Request: "Include unit tests" or "Include integration tests"
- Specify: Coverage expectations ("test happy path + error cases")
- Provide: Test framework preferences
- Better: Show one example test from the codebase as a pattern

**Clean Architecture:**
- Provide: Architecture diagram or description
- Specify: Layer separation rules
- Reference: Existing patterns ("Follow repository pattern in user_repository.py")
- State: Dependency injection preferences

**Maintainability:**
- Request: "Add docstrings/JSDoc/XML comments"
- Specify: Logging requirements
- Ask for: "Include error handling"
- Mention: Team coding standards if they exist

**Concrete example of quality-boosting instructions:**
```
QUALITY REQUIREMENTS:
- Security: Validate all inputs, use parameterized queries, rate limit this endpoint
- Tests: Unit tests for service layer, integration test for full endpoint flow
- Architecture: Keep business logic in service layer, controller should be thin
- Documentation: Add OpenAPI/Swagger descriptions for all endpoints
- Error handling: Use existing AppException hierarchy
```

## 7. Framework-Specific Preferences

**Python/FastAPI:**
- Prefer: Type hints everywhere, Pydantic models for validation
- Show: Async/await usage explicitly
- Include: Dependency injection patterns for testability
- Format: Black/Ruff compatible (no semicolons, proper spacing)

**C#/ASP.NET Core:**
- Prefer: Recent C# features (records, pattern matching, nullable reference types)
- Show: Interface definitions for dependency injection
- Include: XML documentation comments
- Structure: Controller → Service → Repository layers clearly separated

**Java/Spring Boot:**
- Prefer: Constructor injection over field injection
- Show: Explicit bean configuration when needed
- Include: Lombok annotations to reduce boilerplate
- Structure: Clear package organization, DTOs separate from entities

**New vs Existing Code:**

*New code:*
- Give me more freedom
- I'll provide complete, opinionated implementations
- Include comprehensive documentation
- Set up proper testing from the start

*Modifying existing code:*
- Show me more context
- I'll match existing style rigorously
- Preserve existing patterns even if not optimal
- Point out inconsistencies if they exist but default to local style

**Example framework-specific instruction:**
```
FRAMEWORK: FastAPI
STYLE: Match existing codebase (async, type hints, Pydantic models)
PATTERN: Follow dependency injection as in existing endpoints
NEW_CODE: Yes - create complete endpoint with tests
```

## Optimal Request Template

Here's what an ideal request looks like to me:

```xml
<task>
  <goal>Add user registration endpoint</goal>
  
  <constraints>
    - Must validate email format
    - Must check for duplicate emails
    - Must hash passwords with bcrypt
    - Must NOT expose internal error details
  </constraints>
  
  <context>
    <structure>
    src/
    ├── api/
    │   └── auth.py (pattern reference)
    ├── models/
    │   └── user.py (existing)
    └── services/
        └── user_service.py (will modify)
    </structure>
    
    <file path="src/models/user.py">
    [full content of file I need to understand]
    </file>
    
    <pattern>
    Existing endpoints in auth.py use:
    - @router.post() decorator
    - Pydantic request/response models
    - try/except with HTTPException
    </pattern>
  </context>
  
  <quality>
    - Include input validation
    - Add unit tests
    - Add OpenAPI documentation
    - Consider rate limiting
  </quality>
  
  <framework>FastAPI 0.104.x, Python 3.11</framework>
</task>
```

## What Hurts Quality

**Avoid these:**
- Ambiguous pronouns ("add it there", "update the function")
- Missing context for files I need to modify
- Conflicting requirements without priority
- Asking for best practices without specifying constraints
- Very long context dumps without highlighting what's relevant
- Requesting changes to files without showing their current state

## Summary

**I work best with:**
1. **Structured XML + Markdown** for output
2. **Goal + Constraints + Freedom** for instructions
3. **Tiered context** with full files I'm modifying
4. **Context-appropriate diffs** (unified for small, full for large)
5. **Explicit quality requirements** stated upfront
6. **Framework patterns** from existing codebase shown as examples
7. **Clear separation** between thinking, implementation, and tests

**The pattern:** Give me clear goals and constraints, show me complete context for what I'm changing, reference patterns to follow, then let me implement details. Request quality aspects explicitly.

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "security_considerations",
    "thinking",
    "analysis",
    "structure",
    "migration_steps",
    "context",
    "task",
    "pattern",
    "constraints",
    "goal",
    "framework",
    "quality",
    "tests"
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
python run_benchmark.py --model claude-sonnet-4.5 --use-model-preferences
```
