#!/usr/bin/env python3
"""
Adaptive Prompting - Phase 2 of Meta-Prompting Experiment

This module loads model preference profiles and adapts prompts accordingly.
It transforms base prompts to match each model's self-reported preferences.

Usage:
    from adaptive_prompting import adapt_prompt_for_model
    
    adapted = adapt_prompt_for_model(base_prompt, model="gpt-4o")
"""

import json
import re
import yaml
from pathlib import Path
from typing import Dict, Optional


PILOT_DIR = Path(__file__).parent
PREFERENCES_DIR = PILOT_DIR / "model_preferences"


def load_model_preferences(model: str) -> Optional[Dict]:
    """
    Load preference profile for a model.
    
    Args:
        model: Model identifier (e.g., "gpt-4o", "claude-sonnet-4.5")
    
    Returns:
        Dictionary with preferences, or None if profile doesn't exist
    """
    # Sanitize model name for filename
    safe_model = model.replace(":", "-").replace("/", "-")
    filepath = PREFERENCES_DIR / f"{safe_model}.md"
    
    if not filepath.exists():
        return None
    
    content = filepath.read_text()
    
    # Extract YAML front-matter
    yaml_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
    if not yaml_match:
        return None
    
    try:
        metadata = yaml.safe_load(yaml_match.group(1))
        
        # Also extract the full response
        response_match = re.search(r'## Model Response\n\n(.*?)\n\n## Structured', content, re.DOTALL)
        if response_match:
            metadata['full_response'] = response_match.group(1)
        
        return metadata
    except Exception as e:
        print(f"Warning: Could not parse preferences for {model}: {e}")
        return None


def wrap_in_xml_tags(prompt: str, model: str) -> str:
    """
    Wrap prompt sections in XML tags for models that prefer structured output.
    
    Primarily for Claude models that prefer <thinking>, <code>, etc.
    """
    # Add XML structure hints
    wrapped = f"""Please structure your response using XML tags for clarity:

<thinking>
Your analysis and reasoning about the task
</thinking>

<implementation>
The actual code changes
</implementation>

<tests>
Test code (if applicable)
</tests>

---

{prompt}

---

Remember to use the XML tags above to structure your response clearly."""
    
    return wrapped


def add_markdown_file_structure(prompt: str) -> str:
    """
    Enhance prompt to encourage markdown code blocks with file paths.
    
    For models that prefer: ### File: path/to/file.py
    """
    structure_hint = """
When providing code, use this format:

### File: path/to/file.py
```python
# Your code here
```

### File: path/to/another.py
```python
# More code
```

---

"""
    return structure_hint + prompt


def add_unified_diff_request(prompt: str) -> str:
    """
    Request unified diff format for models that prefer it.
    """
    diff_hint = """
For code modifications, please provide changes in unified diff format (git-style):

```diff
--- original/file.py
+++ modified/file.py
@@ -10,7 +10,7 @@
 def example():
-    old_code()
+    new_code()
```

---

"""
    return diff_hint + prompt


def add_detailed_step_instructions(prompt: str) -> str:
    """
    Add explicit step-by-step structure for models preferring detailed guidance.
    """
    steps_hint = """
Please follow these steps:

1. Analyze the requirements
2. Plan the implementation approach
3. Write the code with proper error handling
4. Include comprehensive tests
5. Verify all requirements are met

---

"""
    return steps_hint + prompt


def add_thinking_section(prompt: str) -> str:
    """
    Add explicit thinking/reasoning section for models that use it.
    """
    thinking_hint = """
Before providing code, please include a brief analysis section explaining:
- Your understanding of the requirements
- Key design decisions
- Potential edge cases

---

"""
    return thinking_hint + prompt


def adapt_prompt_for_model(base_prompt: str, model: str, verbose: bool = False) -> str:
    """
    Adapt a base prompt according to model's stated preferences.
    
    Args:
        base_prompt: The original task prompt
        model: Model identifier
        verbose: If True, print adaptation steps
    
    Returns:
        Adapted prompt string
    """
    preferences = load_model_preferences(model)
    
    if not preferences:
        if verbose:
            print(f"No preferences found for {model}, using base prompt")
        return base_prompt
    
    adapted = base_prompt
    adaptations_applied = []
    
    # Extract structured preferences
    structured = preferences.get('structured_preferences', {})
    output_format = structured.get('output_format')
    instruction_style = structured.get('instruction_style')
    
    # Also check the full response for keywords
    full_response = preferences.get('full_response', '').lower()
    
    # Apply adaptations based on preferences
    
    # 1. Output format adaptations
    if output_format == 'xml' or 'xml' in full_response:
        adapted = wrap_in_xml_tags(adapted, model)
        adaptations_applied.append('xml_structure')
    
    if output_format == 'markdown' or ('markdown' in full_response and 'file path' in full_response):
        adapted = add_markdown_file_structure(adapted)
        adaptations_applied.append('markdown_file_structure')
    
    if 'unified diff' in full_response or 'git-style' in full_response:
        adapted = add_unified_diff_request(adapted)
        adaptations_applied.append('unified_diff_format')
    
    # 2. Instruction style adaptations
    if instruction_style == 'detailed' or 'step-by-step' in full_response:
        adapted = add_detailed_step_instructions(adapted)
        adaptations_applied.append('detailed_steps')
    
    # 3. Special syntax adaptations
    if '<thinking>' in full_response or '<analysis>' in full_response:
        adapted = add_thinking_section(adapted)
        adaptations_applied.append('thinking_section')
    
    if verbose:
        print(f"Adaptations applied for {model}: {', '.join(adaptations_applied) if adaptations_applied else 'none'}")
    
    return adapted


def get_adaptation_summary(model: str) -> Dict:
    """
    Get a summary of what adaptations would be applied to a model.
    
    Useful for debugging and documentation.
    """
    preferences = load_model_preferences(model)
    
    if not preferences:
        return {"model": model, "preferences_found": False, "adaptations": []}
    
    structured = preferences.get('structured_preferences', {})
    full_response = preferences.get('full_response', '').lower()
    
    adaptations = []
    
    # Check what would be applied
    if structured.get('output_format') == 'xml' or 'xml' in full_response:
        adaptations.append("xml_structure")
    
    if structured.get('output_format') == 'markdown' or ('markdown' in full_response and 'file path' in full_response):
        adaptations.append("markdown_file_structure")
    
    if 'unified diff' in full_response or 'git-style' in full_response:
        adaptations.append("unified_diff_format")
    
    if structured.get('instruction_style') == 'detailed' or 'step-by-step' in full_response:
        adaptations.append("detailed_steps")
    
    if '<thinking>' in full_response or '<analysis>' in full_response:
        adaptations.append("thinking_section")
    
    return {
        "model": model,
        "preferences_found": True,
        "structured_preferences": structured,
        "adaptations": adaptations,
        "cost_to_discover": preferences.get('cost_usd'),
        "timestamp": preferences.get('timestamp'),
    }


if __name__ == "__main__":
    # Quick test
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python adaptive_prompting.py <model>")
        print("\nExample: python adaptive_prompting.py gpt-4o-mini")
        sys.exit(1)
    
    model = sys.argv[1]
    summary = get_adaptation_summary(model)
    
    print(f"\n{'='*70}")
    print(f"Adaptation Summary for: {model}")
    print(f"{'='*70}\n")
    
    if not summary['preferences_found']:
        print("❌ No preference profile found")
        print(f"\nRun: python discover_model_preferences.py --model {model}")
    else:
        print(f"✓ Preference profile found")
        print(f"  Discovered: {summary['timestamp']}")
        print(f"  Cost: ${summary['cost_to_discover']:.4f}")
        print(f"\nStructured preferences:")
        for key, value in summary['structured_preferences'].items():
            print(f"  {key}: {value}")
        print(f"\nAdaptations that will be applied:")
        if summary['adaptations']:
            for adaptation in summary['adaptations']:
                print(f"  ✓ {adaptation}")
        else:
            print("  (none - will use base prompt)")
        
        # Test adaptation
        test_prompt = "Create a REST API endpoint for user registration."
        print(f"\n{'='*70}")
        print("Test Adaptation")
        print(f"{'='*70}\n")
        print("Base prompt:")
        print(f"  {test_prompt}")
        print("\nAdapted prompt preview (first 300 chars):")
        adapted = adapt_prompt_for_model(test_prompt, model, verbose=True)
        print(f"  {adapted[:300]}...")
