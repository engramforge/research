---
model: gemini:gemini-2.5-pro
backend: gemini
timestamp: 2026-02-09T10:43:08.435335
cost_usd: 0.0206
tokens: 1967
structured_preferences:
  output_format: markdown
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: []
---

# Model Preferences: gemini:gemini-2.5-pro

**Generated:** 2026-02-09T10:43:08.435335  
**Cost:** $0.0206  
**Tokens:** 1967

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

Excellent. This is a crucial and highly effective way to establish a baseline for our collaboration. By defining these preferences, you are helping me tune my generation process for maximum accuracy and utility.

Here is a detailed analysis of my preferences, as requested.

---

## My Optimal Working Preferences

### 1. Output Format

**Preferred Format:** Markdown code blocks with file paths.

This is the most robust, readable, and unambiguous format for delivering code. It clearly delineates which code belongs to which file, handles both new files and full file replacements gracefully, and is a standard, well-understood format in developer workflows (e.g., GitHub, documentation).

**Why it's best:**
*   **Clarity:** There is no ambiguity about where the code should go.
*   **Completeness:** It's ideal for providing full, compilable/runnable file contents, which reduces integration errors.
*   **Readability:** It's clean and easy for a human to review.

**Example of my preferred output for a new file:**

````markdown
Here are the new files for the order creation endpoint.

`/app/models/order.py`
```python
from pydantic import BaseModel, Field, conlist
from typing import List, Optional
from datetime import datetime
import uuid

class OrderItem(BaseModel):
    product_id: str
    quantity: int = Field(gt=0, description="Quantity must be greater than 0")
    unit_price: float = Field(gt=0, description="Unit price must be greater than 0")

class OrderCreate(BaseModel):
    items: conlist(OrderItem, min_length=1)
    notes: Optional[str] = None

class OrderResponse(BaseModel):
    id: uuid.UUID
    items: List[OrderItem]
    total_amount: float
    created_at: datetime
    status: str = "PENDING"
```

`/app/api/v1/orders.py`
```python
from fastapi import APIRouter, Depends, HTTPException, status
from typing import List
from datetime import datetime
import uuid

from app.models.order import OrderCreate, OrderResponse
# Assuming an auth dependency exists in app.security
# from app.security import get_current_user 

# Placeholder for auth dependency
def get_current_user():
    # In a real app, this would validate a token and return a user model
    return {"username": "testuser"}

router = APIRouter()

@router.post(
    "/orders",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Orders"]
)
def create_order(
    order: OrderCreate,
    current_user: dict = Depends(get_current_user)
):
    """
    Creates a new order. Requires authentication.
    """
    if not current_user:
        # This check is technically redundant if the dependency raises the error,
        # but it's good practice.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )

    total_amount = sum(item.quantity * item.unit_price for item in order.items)

    # In a real application, you would save this to a database.
    # The database would generate the ID and created_at timestamp.
    new_order_response = OrderResponse(
        id=uuid.uuid4(),
        items=order.items,
        total_amount=total_amount,
        created_at=datetime.utcnow(),
        status="PENDING"
    )

    return new_order_response
```
````

### 2. Instruction Style

**Preferred Style:** A mix of **High-level goals**, **Constraint-based requirements**, and **Example-driven patterns**.

This combination gives me the "what," the "rules," and the "how."

1.  **Start with a High-Level Goal:** This provides the core intent. (e.g., "Add an order creation endpoint.")
2.  **Provide Specific Constraints/Requirements:** This is the most critical part. It defines the boundaries and success criteria. Your example task is a perfect illustration of this, with clear bullet points for models, status codes, and logic.
3.  **(Optional but powerful) Show an Example:** If you have a preferred coding pattern, architectural style, or even just a naming convention, showing a small example is exponentially more effective than trying to describe it in words. (e.g., "Please follow this service/repository pattern from the existing `/users` endpoint.")

The example task you provided is an *excellent* model for this preferred style.

### 3. Context Presentation

**Preferred Format:** A file tree structure with key excerpts, or full file contents for small, relevant files.

Context is my fuel. The more relevant context I have, the better I can integrate code, follow existing patterns, and avoid making incorrect assumptions.

**Optimal Context Presentation:**

```
Project Structure and Key Files:

/app
├── main.py
├── security.py
├── api/
│   └── v1/
│       ├── __init__.py
│       ├── users.py  // Example of an existing endpoint
│       └── orders.py // This is the new file we are adding
└── models/
    ├── __init__.py
    ├── user.py
    └── order.py // This is a new file we are adding

Here is the content of `app/security.py` to show the auth dependency:

`app/security.py`
```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

def get_current_user(token: str = Depends(oauth2_scheme)):
    # In a real app, decode the token, validate it, and fetch user from DB
    if token != "fake-super-secret-token":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return {"username": "user@example.com", "id": 1}
```
```

This format gives me the project layout (so I know where to place files and how to structure imports) and the specific code I need to interact with (like the `get_current_user` dependency).

### 4. Diff Generation

**Preferred Format:** Full file replacement for new or heavily modified files; Unified diff format for small, targeted changes.

*   **Full File Replacement (Generally Preferred):** This is the simplest and least error-prone method. You get a complete, correct file that can be dropped into the project. It's especially useful when changes are spread across a single file or when creating new files. My default output format (Markdown with file paths) is built around this.

*   **Unified Diff Format (Excellent for Precision):** When you need to make a small, surgical change to a large, existing file, a `diff` is the most precise way to represent that change. It's the professional standard (`git diff`) and I can generate it accurately.

**Example of a Diff Request:**
"Modify the `create_order` function in `/app/api/v1/orders.py` to also log the order total. Provide the output as a unified diff."

### 5. Special Syntax or Markers

Yes, using simple markers to delineate sections in your prompt is extremely helpful for my internal parsing.

**Preferred Markers:**
I can work with simple, clear delimiters. Using a format like this helps me structure my thinking and processing:

```
[TASK]
A high-level description of the goal.
Add a new endpoint for X.

[CONTEXT]
<File tree or relevant code snippets go here>
`path/to/existing_file.py`
```python
#... code ...
```

[INSTRUCTIONS]
- Detailed, bullet-point requirements.
- Must use Pydantic model X.
- Must return status code 201.
- Must not allow negative values.

[OUTPUT_FORMAT]
- Please provide full files for all new code.
- Please provide a unified diff for changes to `path/to/existing_file.py`.
```

While not strictly necessary, this structure helps me compartmentalize the information and ensures I don't mistake an instruction for context, or vice-versa.

### 6. Quality Optimization

Explicitly asking for these qualities is the best way to get them.

*   **Security:** Mention specific threats or requirements.
    *   *Good:* "Ensure the endpoint is protected against unauthorized access."
    *   *Better:* "Use the `get_current_user` dependency for authentication. Validate all input to prevent injection attacks. San

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
python run_benchmark.py --model gemini:gemini-2.5-pro --use-model-preferences
```
