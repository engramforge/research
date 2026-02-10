---
model: gemini:gemini-3-flash-preview
backend: gemini
timestamp: 2026-02-09T10:43:28.507762
cost_usd: 0.0040
tokens: 1221
structured_preferences:
  output_format: xml
  instruction_style: high_level
  context_presentation: None
  diff_generation: None
  special_syntax: ["T", "thinking"]
---

# Model Preferences: gemini:gemini-3-flash-preview

**Generated:** 2026-02-09T10:43:28.507762  
**Cost:** $0.0040  
**Tokens:** 1221

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

To provide the highest quality enterprise-grade code across FastAPI, ASP.NET Core, and Spring Boot, I have analyzed my internal processing patterns. Below is my preferred **Preference Profile**. Following these guidelines will minimize hallucinations, ensure architectural consistency, and produce "copy-paste ready" code.

---

## 1. Output Format: Markdown with XML File Tags
While Markdown is standard, wrapping code in XML-style tags is the most robust way to handle multi-file generation. It allows me to clearly delineate where one file ends and another begins.

*   **Preferred Format:**
    ```xml
    <file path="app/models/order.py">
    ```python
    # Code here...
    ```
    </file>
    ```
*   **Why:** This prevents ambiguity when generating multiple files and makes it easier for you (or an automated script) to parse the output.

## 2. Instruction Style: Constraint-Based + Example-Driven
I perform best when given a **"Sandwich" approach**:
1.  **High-level Goal:** "Add an orders endpoint."
2.  **Constraints (The "Must-Haves"):** "Must use `Depends` for auth," "Must use `Decimal` for currency," "Must include `logging`."
3.  **Example Pattern:** "Follow the repository pattern used in `users_repository.py`."

**Why:** Constraints prevent me from taking "lazy" shortcuts (like skipping error handling), while examples ensure I match your existing project's "flavor" (e.g., naming conventions, folder structure).

## 3. Context Presentation: "Map and Content"
To avoid "losing the thread" in large codebases, please provide:
1.  **The Map:** A brief directory tree of the relevant module.
2.  **The Content:** Full file contents for files I need to *modify*.
3.  **The Reference:** Signatures or interfaces for files I only need to *call*.

**Why:** If I only see a snippet, I might miss an existing import or utility function, leading to redundant code.

## 4. Diff Generation: Full File Replacement (or Search/Replace)
*   **For small/medium files:** Provide the **Full File**. It is much safer and prevents indentation errors.
*   **For very large files (>300 lines):** Use a **Search/Replace block** format:
    ```text
    <<<< SEARCH
    old_code_here
    ====
    new_code_here
    >>>>
    ```
**Why:** Standard Git diffs are prone to "hallucinated" line numbers. Full file replacement is the most reliable way to ensure the code is syntactically correct.

## 5. Special Syntax: The `<thinking>` Tag
I highly recommend allowing me to use a `<thinking>` block before the code.
*   **Usage:** I will use this to map out the dependency graph, identify potential edge cases (e.g., "What if the item list is empty?"), and plan the imports.
*   **Why:** Forcing a "Chain of Thought" significantly reduces logic errors in complex enterprise tasks like transaction management or security middleware.

## 6. Quality Optimization: Explicit "Enterprise" Requirements
To ensure the code isn't just "functional" but "production-ready," please explicitly trigger these requirements in your prompt:
*   **"Include Logging & Telemetry":** I will add structured logging (e.g., Loguru, Serilog, or SLF4J).
*   **"Global Exception Handling":** I will ensure the code doesn't leak stack traces and returns consistent error schemas.
*   **"Input Validation":** I will use the framework's best practices (Pydantic, DataAnnotations, or Bean Validation).
*   **"Unit Tests":** Specify if you want Pytest, xUnit, or JUnit/Mockito.

## 7. Framework-Specific Preferences

### Python (FastAPI)
*   **Preference:** Use **Type Hints** everywhere. Use `Annotated` for dependencies.
*   **Standard:** Pydantic v2 is my default unless v1 is specified.

### C# (ASP.NET Core)
*   **Preference:** Use **File-scoped namespaces** and **Primary Constructors** (C# 12) if your environment supports it.
*   **Standard:** I prefer `Result<T>` patterns or explicit DTOs over returning raw Entities.

### Java (Spring Boot)
*   **Preference:** Use **Lombok** to reduce boilerplate and **Records** for DTOs (Java 17+).
*   **Standard:** Constructor injection over `@Autowired` field injection.

---

## Example of an Optimal Prompt based on these preferences:

> **Task:** Add `/api/v1/orders` endpoint.
>
> **Context:**
> ```text
> app/
> ├── main.py
> ├── dependencies.py
> └── schemas/
>     └── user.py
> ```
> [Full content of dependencies.py provided here]
>
> **Constraints:**
> - Use `<thinking>` tags to plan the logic.
> - Use Pydantic v2 for validation.
> - Total amount must be calculated on the server, not accepted from the client.
> - Use the `get_current_user` dependency from `dependencies.py`.
>
> **Output Format:** Please use `<file path="...">` tags.

---

**By following this profile, you will receive code that is architecturally sound, consistent with your existing codebase, and ready for a production Pull Request.**

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "high_level",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "T",
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
python run_benchmark.py --model gemini:gemini-3-flash-preview --use-model-preferences
```
