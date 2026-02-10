---
model: cloud:deepseek-v3.2
backend: ollama_cloud
timestamp: 2026-02-09T10:24:43.567677
cost_usd: 0.0179
tokens: 2752
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["thinking", "file"]
---

# Model Preferences: cloud:deepseek-v3.2

**Generated:** 2026-02-09T10:24:43.567677  
**Cost:** $0.0179  
**Tokens:** 2752

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

# Code Generation Preference Analysis

## 1. Output Format
**Preferred: Markdown code blocks with file paths**

Why:
- Most practical for developers to copy/paste directly
- Maintains readability in chat interfaces
- Allows clear separation between multiple files
- Can include explanatory text between code blocks

Example:
```python:app/api/v1/endpoints/orders.py
# Code here
```

**Secondary preference: XML tags for complex multi-file changes**
- `<file>` tags work well for bundling multiple files in one response
- `<thinking>` tags help separate reasoning from final output
- Structured but can be verbose

## 2. Instruction Style
**Preferred: Constraint-based with example-driven patterns**

Why:
- Constraints eliminate ambiguity: "must use JWT auth", "must validate with Pydantic"
- Examples show preferred patterns without over-constraining implementation
- Allows creativity within boundaries

Optimal mix:
1. High-level goal statement
2. Must/must not constraints
3. Example patterns for complex logic
4. Step-by-step only for security-critical sections

## 3. Context Presentation
**Preferred: File tree structure with key excerpts**

Why:
- Full files are overwhelming and waste tokens
- Minimal context leads to wrong assumptions
- Tree structure shows project organization
- Key excerpts provide necessary patterns

Example format:
```
project/
├── app/
│   ├── api/
│   │   └── v1/
│   │       ├── endpoints/
│   │       │   └── users.py  # Existing auth patterns
│   │       └── dependencies.py  # Auth dependencies
│   └── models/
│       └── schemas.py  # Existing Pydantic models
```

With key excerpts:
```python:app/api/v1/endpoints/users.py
# Excerpt showing existing auth pattern:
@router.post("/users", dependencies=[Depends(get_current_user)])
async def create_user(...):
```

## 4. Diff Generation
**Preferred: Full file replacement for new files, unified diff for modifications**

Why:
- New files are easier to present in full
- Existing file modifications need context - unified diff shows exactly what changed
- Inline comments get lost in copy/paste

Example for modifications:
```diff:app/api/v1/endpoints/orders.py
@@ -5,6 +5,10 @@ from app.api import deps
 router = APIRouter(prefix="/orders", tags=["orders"])

+@router.post("/")
+async def create_order(...):
+    ...
```

## 5. Special Syntax or Markers
**Helpful markers:**

1. **Instruction vs Context separation:**
   ```
   ## Task Requirements
   [requirements here]
   
   ## Existing Context
   [context here]
   ```

2. **Thinking process (when requested):**
   ```thinking
   Reasoning about implementation choices...
   ```

3. **Multiple file handling:**
   Use clear headings with file paths:
   ```
   ## File: app/api/v1/endpoints/orders.py
   
   ## File: tests/test_orders.py
   ```

4. **TODOs for human review:**
   ```python
   # TODO: Configure actual database connection
   # TODO: Add rate limiting in production
   ```

## 6. Quality Optimization
**Specific guidance needed:**

**Security:**
- Explicitly state: "Validate all inputs", "Use parameterized queries", "Implement proper auth"
- Specify security requirements: "Must use bcrypt for passwords", "Must validate JWT signatures"

**Test coverage:**
- Provide specific test cases: "Test invalid input X", "Test edge case Y"
- Specify test structure: "Use pytest fixtures", "Mock external dependencies"

**Clean architecture:**
- Reference patterns: "Follow repository pattern", "Use dependency injection"
- Specify layer boundaries: "Business logic in service layer", "Data access in repository"

**Maintainability:**
- Ask for: "Add docstrings", "Follow existing naming conventions", "Add type hints"
- Specify: "Extract constants", "Use configuration files"

## 7. Framework-Specific Preferences

**Python/FastAPI:**
- Prefer Pydantic v2 patterns
- Use async/await consistently
- Follow FastAPI project structure (routers, dependencies, models)
- Use `@router` decorators with tags

**C#/ASP.NET Core:**
- Prefer minimal APIs or controller-based based on context
- Use dependency injection with interfaces
- Follow .NET naming conventions (PascalCase)
- Use `[ApiController]` attributes

**Java/Spring Boot:**
- Prefer constructor injection
- Use Lombok annotations if established in project
- Follow package structure (controller, service, repository)
- Use ResponseEntity for responses

**Backend APIs vs Frontend:**
- Backend: Focus on validation, security, data integrity
- Frontend: Need component structure, state management patterns

**New vs Existing Code:**
- New code: Need architectural context
- Existing code: Need to match existing patterns exactly

## Example Implementation Preference

Given the example task, I'd prefer:

1. **Instructions formatted as:**
   ```
   ## Task
   Add orders endpoint with validation and auth
   
   ## Must
   - Use existing auth dependency pattern from users.py
   - Validate with Pydantic models
   - Return appropriate HTTP status codes
   
   ## Example Pattern
   See users.py for auth dependency usage
   ```

2. **Context provided as:**
   ```
   ## Project Structure
   app/
   ├── api/
   │   └── v1/
   │       ├── endpoints/
   │       │   ├── users.py  # Has auth examples
   │       │   └── orders.py  # To create
   │       └── dependencies.py  # Auth functions
   └── models/
       └── schemas.py  # Add order schemas here
   
   ## Key Excerpt: users.py auth pattern
   ```python
   @router.post("/", dependencies=[Depends(get_current_user)])
   async def create_user(...):
   ```
   ```

3. **Output as:**
   ```python:app/models/schemas.py
   # Added Order schemas
   class OrderItem(BaseModel):
       product_id: str
       quantity: conint(gt=0)
       unit_price: confloat(gt=0)
   
   class OrderCreate(BaseModel):
       items: conlist(OrderItem, min_length=1)
       notes: Optional[str] = None
   
   class OrderResponse(BaseModel):
       id: UUID
       items: List[OrderItem]
       total_amount: float
       created_at: datetime
       status: str
   ```

This approach balances clarity with efficiency and produces code that integrates well with existing projects.

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "thinking",
    "file"
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
python run_benchmark.py --model cloud:deepseek-v3.2 --use-model-preferences
```
