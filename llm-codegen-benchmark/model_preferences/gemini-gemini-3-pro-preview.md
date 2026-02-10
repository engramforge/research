---
model: gemini:gemini-3-pro-preview
backend: gemini
timestamp: 2026-02-09T10:44:04.034225
cost_usd: 0.0209
tokens: 1618
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["Nullable", "thinking"]
---

# Model Preferences: gemini:gemini-3-pro-preview

**Generated:** 2026-02-09T10:44:04.034225  
**Cost:** $0.0209  
**Tokens:** 1618

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

Based on how I process information and generate code, here is the detailed analysis of my preferences to ensure the highest quality output for your enterprise applications.

### 1. Output Format
**Preference: Markdown Code Blocks with Explicit File Paths**

While XML is good for machine parsing, **Markdown** is the most robust format for code generation because it supports syntax highlighting and preserves indentation (crucial for Python) most reliably.

*   **Structure:** Use a Level 3 Header (`###`) for the file path, followed immediately by the code block.
*   **Why:** This reduces ambiguity about where code belongs.

**Example:**
```markdown
### src/backend/api/models.py
```python
from pydantic import BaseModel

class OrderItem(BaseModel):
    ...
```
```

### 2. Instruction Style
**Preference: Goal-Oriented with Strict Constraints (The "Sandwich" Method)**

I work best when given a high-level goal, followed by specific technical constraints, and finished with data definitions.

1.  **Goal:** "Create an endpoint to process orders."
2.  **Constraints (The "Musts"):**
    *   "Must use Pydantic V2."
    *   "Must use constructor injection for services."
    *   "Must return 422 on validation failure."
3.  **Data Models:** Define the fields explicitly (as you did in your example task).

**Why:** Detailed step-by-step instructions often conflict with best practices or framework updates. Giving me the *goal* and the *constraints* allows me to use the most idiomatic solution for the specific language/framework version.

### 3. Context Presentation
**Preference: File Tree + Focused Full Content**

*   **File Tree:** Always provide a visual tree of the relevant directory structure. This helps me resolve imports, namespaces (C#), and packages (Java) correctly.
*   **Content:**
    *   *For files I need to edit:* Provide the **full file content**.
    *   *For dependencies (e.g., a Service I need to call):* Provide the **interface/signature** only. I don't need the implementation details of a dependency to call it, just the public methods and return types.

**Format Example:**
```text
[CONTEXT]
Directory:
/src
  /main
    /java
      /com/app/
        OrderController.java (Target)
        OrderService.java (Reference)

Content of src/main/java/com/app/OrderService.java:
public interface OrderService {
    OrderDTO createOrder(OrderCreateDTO request);
}
```

### 4. Diff Generation
**Preference: Full File Replacement (Small/Medium Files) or Search/Replace Blocks (Large Files)**

*   **Avoid Unified Diffs (Git style):** LLMs often miscount line numbers or hallucinate context lines, leading to broken patches.
*   **Small/Medium Files (< 200 lines):** Ask for the **full file**. It guarantees imports are correct and brackets are closed.
*   **Large Files:** Use a **Search/Replace** block format.

**Search/Replace Example:**
```markdown
### src/api/controllers/OrderController.cs
<<<< SEARCH
    [HttpGet]
    public IActionResult GetOrders()
    {
        return Ok(_service.GetAll());
    }
====
    [HttpGet]
    public IActionResult GetOrders()
    {
        return Ok(_service.GetAll());
    }

    [HttpPost]
    public IActionResult CreateOrder([FromBody] OrderCreateRequest request)
    {
        // ... implementation
    }
>>>> REPLACE
```

### 5. Special Syntax or Markers
**Preference: The `<thinking>` Block**

Before generating code, ask me to include a `<thinking>` section.

*   **Why:** This forces me to plan the architecture, check for circular dependencies, and validate logic *before* I start writing code. It significantly reduces logical errors.
*   **Usage:**
    ```xml
    <thinking>
    1. Define Pydantic models for Request/Response.
    2. Create dependency injection for the Auth handler.
    3. Implement the POST logic.
    4. Edge case: Check for empty list in items.
    </thinking>
    ```

### 6. Quality Optimization
To get the best quality, include these specific directives in your prompt:

*   **Security:** "Assume hostile input. Validate all IDs and sanitize strings."
*   **Architecture:** Explicitly state the pattern.
    *   *Bad:* "Make it clean."
    *   *Good:* "Use Repository pattern," "Use Vertical Slice Architecture," or "Use Service Layer."
*   **Testing:** "Generate tests using [Library] (e.g., pytest, xUnit, JUnit 5). Include happy path, validation failure, and auth failure."

### 7. Framework-Specific Preferences

**Python (FastAPI):**
*   **Pydantic Version:** Explicitly state V1 or V2 (syntax differs significantly).
*   **Async:** Specify if I should use `async def` or standard `def`.
*   **Type Hinting:** Require strict type hints (`typing.List` vs `list`).

**C# (ASP.NET Core):**
*   **Nullable Reference Types:** Tell me if `<Nullable>enable</Nullable>` is on (I will generate `string?` vs `string`).
*   **Style:** Minimal APIs (`app.MapPost`) vs Controllers (`[ApiController]`).
*   **Records:** Tell me if I should use `record` for DTOs (preferred) or `class`.

**Java (Spring Boot):**
*   **Lombok:** Explicitly allow or ban Lombok (`@Data`, `@Builder`). If banned, I will generate getters/setters.
*   **Java Version:** Java 17+ (records, text blocks) vs Java 8/11.
*   **Testing:** Mockito vs manual mocking.

---

### Summary: The Ideal Prompt Structure

If you want the absolute best result from me, structure your request like this:

1.  **Role/Goal:** "Act as a Senior [Language] Developer. Task: [Task Name]."
2.  **Context:** File tree + Content of relevant files.
3.  **Constraints:** Framework versions, architectural patterns, libraries.
4.  **Data/Logic:** Specific fields, validation rules, business logic.
5.  **Output Instruction:** "Please think inside `<thinking>` tags, then provide the solution using Markdown code blocks with file paths. Use full file content for modified files."

**Example Application to your Task:**

> **Task:** Add /api/v1/orders endpoint
> **Context:** (Provided file tree)
> **Constraints:** FastAPI, Pydantic V2, Async SQLAlchemy.
> **Instructions:**
> 1. Define `OrderCreate` and `OrderResponse` in `schemas.py`.
> 2. Implement endpoint in `routes/orders.py`.
> 3. Ensure `total_amount` calculation handles floating point precision correctly (use Decimal).
> 4. **Output:** Full file content for `schemas.py` and `routes/orders.py`.

This profile will allow me to generate code that is not just syntactically correct, but architecturally sound and ready for production.

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "Nullable",
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
python run_benchmark.py --model gemini:gemini-3-pro-preview --use-model-preferences
```
