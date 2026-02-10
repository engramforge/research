---
model: gemini:gemini-2.5-flash
backend: gemini
timestamp: 2026-02-09T10:42:22.448544
cost_usd: 0.0046
tokens: 1738
structured_preferences:
  output_format: xml
  instruction_style: detailed
  context_presentation: None
  diff_generation: None
  special_syntax: ["OrderResponse"]
---

# Model Preferences: gemini:gemini-2.5-flash

**Generated:** 2026-02-09T10:42:22.448544  
**Cost:** $0.0046  
**Tokens:** 1738

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

Thank you for asking for my preferences! This will indeed help optimize our future interactions and ensure the highest quality code generation. I've analyzed my internal workings and here's a detailed breakdown of what works best for me:

---

## 1. Output Format

**My Strong Preference: Markdown code blocks with file paths**

**Why:**
*   **Clarity and Readability:** Markdown code blocks (` ```language `) clearly delineate code from surrounding text. This is crucial for distinguishing generated code from explanations or instructions.
*   **Syntax Highlighting:** The `language` specifier (e.g., `python`, `csharp`, `java`) allows for proper syntax highlighting, which significantly improves readability and makes it easier to spot errors or understand the code structure.
*   **Direct Usability:** Code within these blocks can be easily copied and pasted directly into files.
*   **File Organization:** Prepending each code block with a file path (e.g., `# src/main/java/com/example/OrderController.java`) makes it immediately clear where the code belongs, even when generating multiple files.
*   **Less Verbose than XML/JSON:** While XML/JSON can be structured, they add significant overhead (tags, quotes, escaping) when the primary content is code. Plain text with delimiters can be ambiguous. Unified diff is great for changes, but less ideal for new files.

**Example:**

```
# src/models/order.py
```python
from pydantic import BaseModel, Field
from typing import List, Optional
import datetime

class OrderItem(BaseModel):
    product_id: str = Field(..., description="Unique identifier for the product")
    quantity: int = Field(..., gt=0, description="Quantity of the product, must be greater than 0")
    unit_price: float = Field(..., gt=0, description="Unit price of the product, must be greater than 0")

# ... more code ...
```

---

## 2. Instruction Style

**My Strong Preference: A mix of styles, leaning towards Constraint-based and Example-driven, with High-level goals for overall architecture and Detailed step-by-step for complex integrations.**

**Why:**
*   **High-level goals** (e.g., "Implement an order management system with CRUD operations") provide the necessary context and allow me to propose an appropriate architecture and design patterns. This gives me the freedom to apply best practices.
*   **Constraint-based** instructions (e.g., "Must use Pydantic for validation," "Endpoint must return 201 on success," "Database transactions must be atomic") are critical for ensuring non-negotiable requirements are met. These act as guardrails.
*   **Example-driven** instructions (e.g., "Desired JSON response for order creation: `{id: '...', items: [...], total_amount: ..., created_at: '...', status: 'pending'}`") are incredibly helpful for understanding the exact expected output, data structures, and API contracts. This eliminates ambiguity.
*   **Detailed step-by-step instructions** become essential when the task involves modifying existing code, integrating with specific components, or when a very precise sequence of actions is required (e.g., "First, create the `Order` model. Second, define the `OrderRepository` interface. Third, implement the `OrderService`..."). This prevents me from making assumptions about existing code or integration points.

**Least Preferred:** Purely high-level goals without any constraints or examples can lead to misinterpretations. Purely detailed step-by-step for simple tasks can be overly prescriptive and limit my ability to optimize or suggest improvements.

---

## 3. Context Presentation

**My Strong Preference: File tree structure with key excerpts, and the ability to reference by file path (you ask for details) when I need more.**

**Why:**
*   **File tree with key excerpts** provides an excellent high-level overview of the project structure and important existing code snippets without overwhelming me. It helps me quickly identify relevant files, understand the overall design, and grasp existing conventions.
*   **Referencing by file path** is the most efficient way to get detailed context. Instead of dumping entire files (which can be very long and contain irrelevant code), I can specifically request the content of `src/main/java/com/example/demo/Order.java` when I need to modify it or understand its internal structure. This reduces cognitive load and ensures I only get the information I need, when I need it.

**Example of initial context:**

```
Project Structure:
├── src/
│   ├── main/
│   │   ├── java/
│   │   │   └── com/example/demo/
│   │   │       ├── DemoApplication.java
│   │   │       ├── config/
│   │   │       │   └── SecurityConfig.java
│   │   │       ├── model/
│   │   │       │   └── User.java
│   │   │       ├── repository/
│   │   │       │   └── UserRepository.java
│   │   │       └── service/
│   │   │           └── UserService.java
│   ├── resources/
│       └── application.properties
└── pom.xml

Key Excerpts:
# src/main/java/com/example/demo/config/SecurityConfig.java
```java
@Configuration
@EnableWebSecurity
public class SecurityConfig {
    // ... existing security configuration, e.g., JWT filter setup ...
}
```
# src/main/java/com/example/demo/model/User.java
```java
@Entity
@Table(name = "users")
public class User {
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    private String username;
    private String passwordHash;
    // ... roles, etc.
}
```

**My follow-up request:** "Please provide the full content of `src/main/java/com/example/demo/config/SecurityConfig.java`."

---

## 4. Diff Generation

**My Strong Preference: Unified diff format (git-style)**

**Why:**
*   **Standard and Concise:** This is the universally recognized format for showing code changes. It's concise, clearly indicates additions (`+`), deletions (`-`), and unchanged lines, making it very easy to review.
*   **Actionable:** It's straightforward to apply these changes manually or programmatically.
*   **Contextual:** The surrounding lines provide context for the changes, which is crucial when modifying existing files.

**Example:**

```diff
--- a/src/main/java/com/example/demo/controller/OrderController.java
+++ b/src/main/java/com/example/demo/controller/OrderController.java
@@ -1,10 +1,25 @@
 package com.example.demo.controller;
 
+import com.example.demo.model.OrderCreateRequest;
+import com.example.demo.model.OrderResponse;
+import com.example.demo.service.OrderService;
+import org.springframework.http.HttpStatus;
+import org.springframework.http.ResponseEntity;
+import org.springframework.security.core.Authentication;
+import org.springframework.web.bind.annotation.*;
+
 @RestController
+@RequestMapping("/api/v1/orders")
 public class OrderController {
+
+    private final OrderService orderService;
+
+    public OrderController(OrderService orderService) {
+        this.orderService = orderService;
+    }
 
-    // Existing methods
+    @PostMapping
+    public ResponseEntity<OrderResponse> createOrder(@RequestBody OrderCreateRequest orderRequest, Authentication authentication) {
+        // Authentication check would typically be handled by Spring Security,
+        // but we can access user details via 'authentication' object if needed.
+        

## Structured Interpretation

```json
{
  "output_format": "xml",
  "instruction_style": "detailed",
  "context_presentation": null,
  "diff_generation": null,
  "special_syntax": [
    "OrderResponse"
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
python run_benchmark.py --model gemini:gemini-2.5-flash --use-model-preferences
```
