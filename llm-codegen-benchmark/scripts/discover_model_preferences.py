#!/usr/bin/env python3
"""
Discover Model Preferences - Meta-Prompting Experiment

This script asks models about their preferred formats and styles for optimal
code generation. The responses are stored as preference profiles that can be
used to adapt prompts in future benchmark runs.

Usage:
    python discover_model_preferences.py --model gpt-4o
    python discover_model_preferences.py --model claude-sonnet-4.5 --all-tasks
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

# Unified LLM client
from llm_client import call_llm, determine_backend

PILOT_DIR = Path(__file__).parent
PREFERENCES_DIR = PILOT_DIR / "model_preferences"

META_PROMPT_TEMPLATE = """You are about to help generate code for enterprise applications across multiple frameworks:
- Python with FastAPI (REST APIs)
- C# with ASP.NET Core (Web APIs)
- Java with Spring Boot (REST Controllers)

Before we begin actual code generation tasks, I want to understand YOUR preferences for optimal output quality.

Please analyze how you work best and provide guidance on the following aspects:

## 1. Output Format
What format do you prefer for delivering code changes?
- XML tags (e.g., <code>, <file>, <thinking>)
- JSON structure
- Markdown code blocks with file paths
- Unified diff format
- Plain text with clear delimiters
- Other format you prefer

## 2. Instruction Style
What instruction style helps you generate the highest quality code?
- Detailed step-by-step instructions
- High-level goals with freedom to implement
- Constraint-based (must/must not requirements)
- Example-driven (showing desired patterns)
- Mix of styles

## 3. Context Presentation
How should we present existing code context to you?
- Full file contents inline
- File tree structure with key excerpts
- Referenced by file path (you ask for details)
- Minimal context (just the task)
- Comprehensive context dump

## 4. Diff Generation
What's your preferred way to show code modifications?
- Unified diff format (git-style)
- Full file replacement
- Inline comments showing changes
- Side-by-side before/after
- Structured change description

## 5. Special Syntax or Markers
Are there any special tags, markers, or syntax that help you:
- Distinguish between instructions and context?
- Organize your thinking process?
- Structure your output more clearly?
- Handle multiple files?

## 6. Quality Optimization
What additional guidance helps you produce:
- More secure code?
- Better test coverage?
- Cleaner architecture?
- More maintainable code?

## 7. Framework-Specific Preferences
Do you have different preferences for:
- Python/FastAPI vs C#/ASP.NET vs Java/Spring?
- Backend APIs vs frontend code?
- New code vs modifying existing code?

Please provide your response as a detailed analysis. Be honest about what actually helps you generate better code, not what you think we want to hear. Include specific examples where helpful.

Your response will be stored as a preference profile and used to optimize future code generation tasks.
"""


def discover_preferences(model: str, task_context: Optional[str] = None) -> Dict:
    """
    Ask a model about its code generation preferences.
    
    Args:
        model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4.5")
        task_context: Optional specific task context to make preferences more concrete
    
    Returns:
        Dictionary with model response and metadata
    """
    print(f"\n{'='*70}")
    print(f"Discovering preferences for: {model}")
    print(f"{'='*70}\n")
    
    # Build the meta-prompt
    prompt = META_PROMPT_TEMPLATE
    if task_context:
        prompt += f"\n\nFor context, here's an example task you might be asked to complete:\n{task_context}\n"
    
    backend = determine_backend(model)
    
    try:
        response, usage = call_llm(model, prompt, max_tokens=4096)
        
        print(f"✓ Received response ({usage['output_tokens']} tokens)")
        print(f"  Cost: ${usage['estimated_cost_usd']:.4f}")
        
        return {
            "model": model,
            "backend": backend,
            "timestamp": datetime.now().isoformat(),
            "prompt": prompt,
            "response": response,
            "usage": usage,
            "task_context": task_context,
        }
        
    except Exception as e:
        print(f"✗ Error: {e}")
        raise


def parse_preferences(response: str) -> Dict:
    """
    Extract structured preferences from model response.
    
    This is a simple heuristic parser - could be enhanced with LLM-based parsing.
    """
    preferences = {
        "output_format": None,
        "instruction_style": None,
        "context_presentation": None,
        "diff_generation": None,
        "special_syntax": [],
        "quality_tips": [],
        "framework_specific": {},
    }
    
    # Simple keyword extraction (could be made more sophisticated)
    response_lower = response.lower()
    
    # Output format detection
    if "xml" in response_lower and ("tag" in response_lower or "<" in response):
        preferences["output_format"] = "xml"
    elif "json" in response_lower:
        preferences["output_format"] = "json"
    elif "markdown" in response_lower:
        preferences["output_format"] = "markdown"
    elif "diff" in response_lower and "unified" in response_lower:
        preferences["output_format"] = "unified_diff"
    
    # Instruction style detection
    if "step-by-step" in response_lower or "detailed" in response_lower:
        preferences["instruction_style"] = "detailed"
    elif "high-level" in response_lower or "freedom" in response_lower:
        preferences["instruction_style"] = "high_level"
    elif "constraint" in response_lower:
        preferences["instruction_style"] = "constraint_based"
    
    # Special syntax extraction (look for mentioned tags/markers)
    import re
    tag_pattern = r'<(\w+)>'
    tags = re.findall(tag_pattern, response)
    if tags:
        preferences["special_syntax"] = list(set(tags))
    
    return preferences


def save_preference_profile(data: Dict, model: str) -> Path:
    """
    Save preference profile as markdown with YAML front-matter.
    """
    PREFERENCES_DIR.mkdir(exist_ok=True)
    
    # Sanitize model name for filename
    safe_model = model.replace(":", "-").replace("/", "-")
    filepath = PREFERENCES_DIR / f"{safe_model}.md"
    
    # Parse structured preferences
    structured = parse_preferences(data["response"])
    
    # Create markdown document with YAML front-matter
    content = f"""---
model: {data['model']}
backend: {data['backend']}
timestamp: {data['timestamp']}
cost_usd: {data['usage']['estimated_cost_usd']:.4f}
tokens: {data['usage']['output_tokens']}
structured_preferences:
  output_format: {structured['output_format']}
  instruction_style: {structured['instruction_style']}
  context_presentation: {structured['context_presentation']}
  diff_generation: {structured['diff_generation']}
  special_syntax: {json.dumps(structured['special_syntax'])}
---

# Model Preferences: {data['model']}

**Generated:** {data['timestamp']}  
**Cost:** ${data['usage']['estimated_cost_usd']:.4f}  
**Tokens:** {data['usage']['output_tokens']}

## Meta-Prompt Used

```
{data['prompt'][:500]}...
[Full prompt truncated for brevity]
```

## Model Response

{data['response']}

## Structured Interpretation

```json
{json.dumps(structured, indent=2)}
```

## Notes

This preference profile was auto-generated by asking the model about its own preferences.
It may be updated over time as we learn more about optimal prompting strategies.

To use these preferences in a benchmark run:
```bash
python run_benchmark.py --model {data['model']} --use-model-preferences
```
"""
    
    filepath.write_text(content)
    print(f"\n✓ Saved preference profile: {filepath}")
    
    return filepath


def load_example_task(task_id: str = "fastapi-001") -> str:
    """Load an example task to provide context to the model."""
    from pathlib import Path
    import yaml
    
    # Find task file
    suites_dir = PILOT_DIR.parent / "suites"
    task_files = list(suites_dir.rglob(f"*/{task_id}.yaml"))
    
    if not task_files:
        return None
    
    with open(task_files[0]) as f:
        task = yaml.safe_load(f)
    
    context = f"Task: {task.get('description', 'N/A')}\n"
    if task.get('requirements'):
        context += "\nRequirements:\n"
        for req in task['requirements']:
            context += f"- {req}\n"
    
    return context


def main():
    parser = argparse.ArgumentParser(description="Discover model preferences for code generation")
    parser.add_argument("--model", required=True, help="Model to query (e.g., gpt-4o, claude-sonnet-4.5)")
    parser.add_argument("--task", default="fastapi-001", help="Example task ID for context (default: fastapi-001)")
    parser.add_argument("--no-context", action="store_true", help="Don't include task context in meta-prompt")
    parser.add_argument("--output", help="Custom output path (default: model_preferences/{model}.md)")
    
    args = parser.parse_args()
    
    # Load task context if requested
    task_context = None
    if not args.no_context:
        try:
            task_context = load_example_task(args.task)
            if task_context:
                print(f"Including context from task: {args.task}")
        except Exception as e:
            print(f"Warning: Could not load task context: {e}")
    
    # Discover preferences
    try:
        data = discover_preferences(args.model, task_context)
        
        # Save profile
        if args.output:
            output_path = Path(args.output)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(data, indent=2))
            print(f"\n✓ Saved raw data: {output_path}")
        
        # Save as formatted markdown
        profile_path = save_preference_profile(data, args.model)
        
        print(f"\n{'='*70}")
        print("SUCCESS: Preference profile created!")
        print(f"{'='*70}")
        print(f"\nView profile: cat {profile_path}")
        print(f"\nNext steps:")
        print(f"  1. Review the profile to validate preferences make sense")
        print(f"  2. Run benchmark with preferences: python run_benchmark.py --model {args.model} --use-model-preferences")
        print(f"  3. Compare results against baseline")
        
    except Exception as e:
        print(f"\n✗ FAILED: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
