---
model: gpt-4o-mini
backend: openai
timestamp: 2026-02-06T23:50:06.921509
cost_usd: 0.0006
tokens: 876
structured_preferences:
  output_format: markdown
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: []
---

# Model Preferences: gpt-4o-mini

**Generated:** 2026-02-06T23:50:06.921509  
**Cost:** $0.0006  
**Tokens:** 876

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

Certainly! Here’s a detailed analysis of how I work best for generating high-quality code across the specified frameworks:

## 1. Output Format
**Preferred Format:** Markdown code blocks with file paths.

**Reasoning:** 
- Markdown is widely used and easily readable, making it suitable for sharing code snippets.
- Including file paths helps to contextualize where the code belongs, which is essential for enterprise applications with multiple files and modules.

**Example:**
```markdown
### File: app/main.py
```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
def read_root():
    return {"Hello": "World"}
```
```

## 2. Instruction Style
**Preferred Style:** Mix of styles (Detailed step-by-step instructions + High-level goals).

**Reasoning:**
- Detailed instructions help ensure that specific requirements are met.
- High-level goals provide flexibility in implementation, allowing for creative solutions that may be more efficient or elegant.

**Example:** 
- "Implement a user authentication endpoint that validates JWT tokens (high-level goal). Please include error handling for expired tokens and return a 401 status code (detailed instruction)."

## 3. Context Presentation
**Preferred Context:** Full file contents inline for smaller files, or File tree structure with key excerpts for larger projects.

**Reasoning:**
- Full file contents are useful for smaller files where context is easily digestible.
- For larger projects, a file tree structure with key excerpts allows for a clearer overview without overwhelming detail.

**Example:**
```
src/
├── app/
│   ├── main.py  # Entry point
│   ├── models.py # Database models
│   └── routes/
│       └── user.py # User-related endpoints
```

## 4. Diff Generation
**Preferred Method:** Unified diff format (git-style).

**Reasoning:**
- Unified diff format is a standard in version control systems, making it easy to understand changes.
- It clearly shows what has been added or removed, which is crucial for code reviews and collaboration.

**Example:**
```diff
--- app/routes/user.py
+++ app/routes/user.py
@@ -1,5 +1,6 @@
 from fastapi import APIRouter, HTTPException
+from fastapi.security import OAuth2PasswordBearer

 router = APIRouter()

 @router.post("/token")
```

## 5. Special Syntax or Markers
**Preferred Markers:** Use of clear delimiters for instructions and context.

**Reasoning:**
- Clear delimiters help distinguish between different types of content, making it easier to follow along.

**Example:**
```
# INSTRUCTION START
Implement a new endpoint for user registration.
# INSTRUCTION END

# CONTEXT START
# File: app/routes/user.py
...
# CONTEXT END
```

## 6. Quality Optimization
**Guidance for Quality:**
- **Security:** Emphasize the use of secure coding practices, such as input validation and proper authentication mechanisms.
- **Test Coverage:** Encourage writing unit tests alongside new features, specifying frameworks like pytest for Python or xUnit for C#.
- **Clean Architecture:** Advocate for separation of concerns, using design patterns like MVC or repository patterns.
- **Maintainability:** Suggest clear naming conventions and documentation practices.

**Example:** 
- "Ensure that all new endpoints have corresponding unit tests that cover edge cases."

## 7. Framework-Specific Preferences
**Framework Preferences:**
- **Python/FastAPI:** Favor asynchronous programming patterns and dependency injection.
- **C#/ASP.NET:** Prefer using attributes for routing and middleware for cross-cutting concerns.
- **Java/Spring:** Advocate for using Spring’s built-in features like Spring Security for authentication.

**Backend vs Frontend:** 
- For backend APIs, focus on RESTful principles and proper status code usage.
- For frontend code (if applicable), emphasize responsive design and state management.

**New Code vs Modifying Existing Code:** 
- For new code, encourage following best practices from the start.
- For modifications, provide context on existing architecture to ensure compatibility.

By following these preferences, I can generate code that is not only functional but also secure, maintainable, and aligned with best practices across different frameworks.

## Structured Interpretation

```json
{
  "output_format": "markdown",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [],
  "quality_tips": [],
  "framework_specific": {}
}
```

## Notes

This preference profile was auto-generated by asking the model about its own preferences.
It may be updated over time as we learn more about optimal prompting strategies.

To use these preferences in a benchmark run:
```bash
python run_benchmark.py --model gpt-4o-mini --use-model-preferences
```
