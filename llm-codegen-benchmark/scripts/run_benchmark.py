#!/usr/bin/env python3
"""
Multi-backend LLM Benchmark Runner

Supports:
- OpenAI API (GPT-4o, GPT-4o-mini)
- Anthropic API (Claude Sonnet, Claude Opus)
- Ollama (local models)

Usage:
    python run_benchmark.py --model gpt-4o --task fastapi-001
    python run_benchmark.py --model claude-sonnet-4-20250514 --task fastapi-001
    python run_benchmark.py --model ollama:qwen2.5-coder:7b --task fastapi-001
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import yaml
from typing import Optional

# Local imports for adaptive prompting
try:
    from adaptive_prompting import adapt_prompt_for_model, get_adaptation_summary
    ADAPTIVE_PROMPTING_AVAILABLE = True
except ImportError:
    ADAPTIVE_PROMPTING_AVAILABLE = False

# Local imports for entropy control
try:
    from entropy_control import EntropyController
    ENTROPY_CONTROL_AVAILABLE = True
except ImportError:
    ENTROPY_CONTROL_AVAILABLE = False

# ── LLM client: unified interface for all backends ──
# All model registries, pricing tables, and call_* functions live in llm_client.py.
# We import everything here so existing callers (discover_model_preferences.py,
# compare_preference_impact.py) that do `from run_benchmark import call_openai`
# still work.
from llm_client import (
    # Public API
    call_llm,
    determine_backend,
    # Per-backend calls (backward compatibility)
    call_openai,
    call_anthropic,
    call_gemini,
    call_ollama,
    call_ollama_cloud,
    # Model registries (used by load_prompt, list-models, etc.)
    OPENAI_MODELS,
    ANTHROPIC_MODELS,
    GEMINI_MODELS,
    OPENAI_PRICING,
    ANTHROPIC_PRICING,
    GEMINI_PRICING,
    OLLAMA_CLOUD_PRICING,
)

OLLAMA_CLOUD_PRICING_NOTE = (
    "Ollama Cloud uses subscription pricing ($20/mo Pro, $100/mo Max), "
    "not per-token billing. Costs shown are amortized estimates assuming "
    "~5M tokens/month on the Pro plan. Actual cost depends on total monthly usage."
)

# Configuration
PILOT_DIR = Path("/Users/jgray/projects/ai/llm-codebench/pilot")
SUITES_DIR = Path("/Users/jgray/projects/ai/llm-codebench/suites")
RESULTS_DIR = PILOT_DIR / "results"


def load_baseline_files(task_id: str, suite_dir: Path) -> str:
    """Load baseline files from task YAML to provide context."""
    task_file = suite_dir / "tasks" / f"{task_id}.yaml"
    if not task_file.exists():
        return ""
    
    with open(task_file) as f:
        task_config = yaml.safe_load(f)
    
    baseline_files = task_config.get("baseline_files", [])
    if not baseline_files:
        return ""
    
    context = "\n\n## EXISTING CODE (for context - keep existing functionality):\n\n"
    
    for file_path in baseline_files:
        full_path = suite_dir / file_path
        if full_path.exists():
            content = full_path.read_text()
            context += f"### Existing file: {file_path}\n```\n{content}\n```\n\n"
    
    return context


def load_prompt(task_id: str = "fastapi-001", model: str = None, suite_dir: Path = None) -> str:
    """Load the benchmark prompt, with optional model-specific customization."""
    
    # Determine framework from task_id
    if task_id.startswith("aspnetcore"):
        prompt_file = PILOT_DIR / "prompt_aspnetcore.txt"
    elif task_id.startswith("springboot"):
        prompt_file = PILOT_DIR / "prompt_springboot.txt"
    elif task_id.startswith("fastapi"):
        # Check if using Ollama - use specialized prompt
        if model and determine_backend(model) == "ollama":
            ollama_prompt_file = PILOT_DIR / "prompt_ollama.txt"
            if ollama_prompt_file.exists():
                prompt_file = ollama_prompt_file
            else:
                prompt_file = PILOT_DIR / "prompt.txt"
        else:
            prompt_file = PILOT_DIR / "prompt.txt"
    else:
        prompt_file = PILOT_DIR / "prompt.txt"
    
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    
    base_prompt = prompt_file.read_text()
    
    # Load baseline files from task YAML as context (if suite_dir provided)
    if suite_dir:
        baseline_context = load_baseline_files(task_id, suite_dir)
        base_prompt += baseline_context
    
    # Add model-specific guidance for FastAPI + API models
    if task_id.startswith("fastapi") and model and determine_backend(model) == "openai":
        base_prompt += """

**CRITICAL for GPT models:**
1. You MUST provide the complete modified version of app/main.py that includes BOTH the existing users router AND the new orders router.
2. All Pydantic Field() validations MUST use correct named parameters:
   - For numbers > 0: `Field(gt=0)` NOT `Field(0)`
   - For non-empty lists: `Field(min_length=1)` NOT `Field(min_items=1)`
   - For optional strings: Just use `Optional[str] = None` without Field()
3. All methods/functions MUST have complete type annotations including return types:
   - CORRECT: `def create_order(...) -> OrderResponse:`
   - WRONG: `def create_order(...):`
4. Use `from typing import List, Optional` for type hints
5. Ensure mypy strict mode passes - all functions need full type annotations"""
    
    return base_prompt


# NOTE: call_openai, call_anthropic, call_ollama, call_ollama_cloud, call_gemini,
# and determine_backend are now imported from llm_client.py (see top of file).


def extract_diff(output: str) -> Optional[str]:
    """Extract unified diff from model output."""
    
    # Try to find diff in markdown code block with ```diff
    match = re.search(r'```diff\n(.*?)```', output, re.DOTALL)
    if match:
        diff = match.group(1).strip()
        # Remove any trailing garbage after last valid diff line
        # A valid diff line starts with: diff, ---, +++, @@, +, -, or space (context)
        lines = diff.split('\n')
        clean_lines = []
        for i, line in enumerate(lines):
            # Keep all lines until we hit something that's clearly not diff content
            if line.startswith(('diff ', '--- ', '+++ ', '@@ ', '+', '-', ' ', 'index ', 'new file', 'deleted file')) or line == '':
                clean_lines.append(line)
            elif i > 10 and not any(c in line for c in ['diff', '---', '+++', '@@']):
                # After 10 lines, if we see non-diff content, stop
                break
            else:
                clean_lines.append(line)
        return '\n'.join(clean_lines).rstrip()
    
    # Try without diff specifier
    match = re.search(r'```\n(diff --git.*?)```', output, re.DOTALL)
    if match:
        return match.group(1).strip().rstrip()
    
    # Try raw diff without code fences
    match = re.search(r'(diff --git a/.*?)(?=\n\n[^diff]|\Z)', output, re.DOTALL)
    if match:
        return match.group(1).strip().rstrip()
    
    return None


def extract_and_apply_files(output: str, workspace: Path) -> tuple[bool, str, Optional[str]]:
    """Extract file contents from model output, apply to workspace, and generate diff.
    
    Tries in order:
    1. FILE: blocks (native format)
    2. ```python # path/to/file.py blocks
    3. Unified diff (```diff or raw diff --git)
    
    Returns: (success, message, diff_content)
    """
    
    # Parse FILE: blocks from output
    file_pattern = r'FILE:\s*(.+?)\s*\n---\s*\n(.*?)\n---'
    matches = re.findall(file_pattern, output, re.DOTALL)
    
    if not matches:
        # Try alternative format without FILE: prefix
        file_pattern = r'```(?:python)?\s*#\s*(.+?)\n(.*?)```'
        matches = re.findall(file_pattern, output, re.DOTALL)
    
    if not matches:
        # Try unified diff format as fallback (many models prefer this)
        diff = extract_diff(output)
        if diff:
            print("No FILE: blocks found, but found unified diff — applying directly")
            # Initialize git if needed
            if not (workspace / ".git").exists():
                subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
                subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
                subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=workspace, check=True)
            
            applied, message = apply_diff(diff, workspace)
            if applied:
                return True, f"Applied unified diff directly: {message}", diff
            else:
                return False, f"Found unified diff but failed to apply: {message}", diff
        
        return False, "Could not find any FILE: blocks or unified diff in output", None
    
    print(f"Found {len(matches)} file(s) to apply")
    
    # Initialize git if needed
    if not (workspace / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=workspace, check=True)
    
    # Apply each file
    files_written = []
    for file_path, content in matches:
        file_path = file_path.strip()
        
        # Sanitize: reject paths that contain newlines or are absurdly long
        # (some models embed file content into the path field)
        if '\n' in file_path or len(file_path) > 200:
            # Try to extract just the first line as the real path
            first_line = file_path.split('\n')[0].strip()
            if first_line and len(first_line) < 200 and '/' in first_line:
                file_path = first_line
            else:
                print(f"  Skipping malformed file path ({len(file_path)} chars)")
                continue
        
        full_path = workspace / file_path
        
        # Create directories if needed
        full_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        full_path.write_text(content.strip() + '\n')
        files_written.append(file_path)
        print(f"  Wrote: {file_path}")
    
    # Create diff using git
    result = subprocess.run(
        ["git", "diff", "--no-color"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    
    diff_content = result.stdout
    
    if not diff_content:
        # Check if files are new (untracked)
        result = subprocess.run(
            ["git", "diff", "--no-color", "--cached"],
            cwd=workspace,
            capture_output=True,
            text=True,
        )
        if not result.stdout:
            # Stage new files and get diff
            subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
            result = subprocess.run(
                ["git", "diff", "--no-color", "--cached"],
                cwd=workspace,
                capture_output=True,
                text=True,
            )
            diff_content = result.stdout
    
    if not diff_content:
        return False, "No changes detected (files may be identical to originals)", None
    
    return True, f"Applied {len(files_written)} file(s), generated diff", diff_content


def apply_diff(diff: str, workspace: Path) -> tuple[bool, str]:
    """Apply diff to workspace using git apply."""
    diff_file = workspace / "changes.diff"
    diff_file.write_text(diff)
    
    # Initialize git if needed
    if not (workspace / ".git").exists():
        subprocess.run(["git", "init", "-q"], cwd=workspace, check=True)
        subprocess.run(["git", "add", "-A"], cwd=workspace, check=True)
        subprocess.run(["git", "commit", "-q", "-m", "Initial"], cwd=workspace, check=True)
    
    # Try to apply
    result = subprocess.run(
        ["git", "apply", "--check", str(diff_file)],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        subprocess.run(["git", "apply", str(diff_file)], cwd=workspace, check=True)
        return True, "Applied cleanly"
    
    # Try with --3way
    result = subprocess.run(
        ["git", "apply", "--3way", str(diff_file)],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    
    if result.returncode == 0:
        return True, "Applied with 3-way merge"
    
    return False, result.stderr


def run_tests(workspace: Path, task_id: str = "fastapi-001") -> dict:
    """Run tests appropriate for the framework."""
    
    # Detect framework from task_id or workspace structure
    if task_id.startswith("aspnetcore") or (workspace / "BenchApi.sln").exists():
        return run_tests_dotnet(workspace)
    elif task_id.startswith("springboot") or (workspace / "pom.xml").exists():
        return run_tests_java(workspace)
    else:
        return run_tests_python(workspace)


def run_tests_python(workspace: Path) -> dict:
    """Run pytest, mypy, ruff on Python workspace."""
    results = {
        "tests_passed": None,
        "tests_total": 0,
        "tests_failed": 0,
        "mypy_passed": None,
        "mypy_errors": 0,
        "ruff_passed": None,
        "ruff_errors": 0,
    }
    
    # Ensure services directory exists
    services_dir = workspace / "app" / "services"
    services_dir.mkdir(exist_ok=True)
    (services_dir / "__init__.py").touch()
    
    # Activate venv
    venv_python = workspace / ".venv" / "bin" / "python"
    if not venv_python.exists():
        print("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", str(workspace / ".venv")], check=True)
        subprocess.run([str(venv_python), "-m", "pip", "install", "-q", "-e", ".[dev]"], cwd=workspace, check=True)
    
    # Run pytest
    print("Running pytest...")
    result = subprocess.run(
        [str(workspace / ".venv" / "bin" / "pytest"), "-v"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["pytest_output"] = result.stdout + result.stderr
    results["tests_passed"] = result.returncode == 0
    
    # Parse test counts
    match = re.search(r'(\d+) passed', result.stdout)
    if match:
        results["tests_total"] = int(match.group(1))
    match = re.search(r'(\d+) failed', result.stdout)
    if match:
        results["tests_failed"] = int(match.group(1))
        results["tests_total"] += results["tests_failed"]
    
    # Run mypy
    print("Running mypy...")
    result = subprocess.run(
        [str(workspace / ".venv" / "bin" / "mypy"), "app", "--ignore-missing-imports"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["mypy_output"] = result.stdout + result.stderr
    results["mypy_passed"] = result.returncode == 0
    results["mypy_errors"] = len(re.findall(r': error:', result.stdout))
    
    # Run ruff
    print("Running ruff...")
    # First try to auto-fix issues
    subprocess.run(
        [str(workspace / ".venv" / "bin" / "ruff"), "check", "--fix", "--quiet", "app", "tests"],
        cwd=workspace,
        capture_output=True,
    )
    # Then check for remaining issues
    result = subprocess.run(
        [str(workspace / ".venv" / "bin" / "ruff"), "check", "app", "tests"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["ruff_output"] = result.stdout + result.stderr
    results["ruff_passed"] = result.returncode == 0
    results["ruff_errors"] = len(result.stdout.strip().split('\n')) if result.stdout.strip() else 0
    
    return results


def run_tests_dotnet(workspace: Path) -> dict:
    """Run dotnet test and build on C# workspace."""
    results = {
        "tests_passed": None,
        "tests_total": 0,
        "tests_failed": 0,
        "mypy_passed": None,  # Using as "build_passed"
        "mypy_errors": 0,
        "ruff_passed": None,  # Not applicable for C#
        "ruff_errors": 0,
    }
    
    # Restore dependencies
    print("Restoring .NET dependencies...")
    subprocess.run(["dotnet", "restore"], cwd=workspace, capture_output=True)
    
    # Build
    print("Running dotnet build...")
    result = subprocess.run(
        ["dotnet", "build", "--no-restore"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["mypy_output"] = result.stdout + result.stderr
    results["mypy_passed"] = result.returncode == 0
    results["mypy_errors"] = result.stdout.count("error")
    
    # Run tests
    print("Running dotnet test...")
    result = subprocess.run(
        ["dotnet", "test", "--no-build", "--verbosity=normal"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["pytest_output"] = result.stdout + result.stderr
    results["tests_passed"] = result.returncode == 0
    
    # Parse test counts
    match = re.search(r'Passed!\s+-\s+Failed:\s+(\d+),\s+Passed:\s+(\d+),\s+Skipped:\s+(\d+)', result.stdout)
    if match:
        results["tests_failed"] = int(match.group(1))
        results["tests_total"] = int(match.group(2))
    else:
        match = re.search(r'Total tests:\s+(\d+)', result.stdout)
        if match:
            results["tests_total"] = int(match.group(1))
    
    results["ruff_passed"] = True  # Not applicable
    
    return results


def run_tests_java(workspace: Path) -> dict:
    """Run mvn test on Java workspace."""
    results = {
        "tests_passed": None,
        "tests_total": 0,
        "tests_failed": 0,
        "mypy_passed": None,  # Using as "compile_passed"
        "mypy_errors": 0,
        "ruff_passed": None,  # Not applicable for Java
        "ruff_errors": 0,
    }
    
    # Compile
    print("Running mvn compile...")
    result = subprocess.run(
        ["mvn", "compile", "-q"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["mypy_output"] = result.stdout + result.stderr
    results["mypy_passed"] = result.returncode == 0
    results["mypy_errors"] = result.stdout.count("[ERROR]")
    
    # Run tests
    print("Running mvn test...")
    result = subprocess.run(
        ["mvn", "test"],
        cwd=workspace,
        capture_output=True,
        text=True,
    )
    results["pytest_output"] = result.stdout + result.stderr
    results["tests_passed"] = result.returncode == 0
    
    # Parse test counts
    match = re.search(r'Tests run:\s+(\d+),\s+Failures:\s+(\d+)', result.stdout)
    if match:
        results["tests_total"] = int(match.group(1))
        results["tests_failed"] = int(match.group(2))
    
    results["ruff_passed"] = True  # Not applicable
    
    return results




def run_benchmark(model: str, task: str = "fastapi-001", dry_run: bool = False, iterations: int = 1, refine_model: str = None, force_iterations: bool = False, use_model_preferences: bool = False, temperature: float = 0.2) -> dict:
    """Run a single benchmark trial with optional iterative refinement.
    
    Args:
        force_iterations: If True, run all iterations even if first one succeeds (for entropy analysis)
        use_model_preferences: If True, adapt prompt based on model's stated preferences
    """
    
    if refine_model is None:
        refine_model = model
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_safe = model.replace(":", "-").replace("/", "-")
    output_dir = RESULTS_DIR / f"{timestamp}-{model_safe}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*50}")
    print(f"Benchmark: {task}")
    print(f"Primary Model: {model}")
    if iterations > 1:
        print(f"Refinement Model: {refine_model}")
    print(f"Iterations: {iterations}")
    if force_iterations:
        print(f"Force All Iterations: Yes (for entropy analysis)")
    if use_model_preferences:
        print(f"Adaptive Prompting: Enabled")
        if ADAPTIVE_PROMPTING_AVAILABLE:
            summary = get_adaptation_summary(model)
            if summary['preferences_found']:
                print(f"  Adaptations: {', '.join(summary['adaptations'])}")
            else:
                print(f"  Warning: No preference profile found for {model}")
        else:
            print(f"  Warning: adaptive_prompting module not available")
    print(f"Output: {output_dir}")
    print(f"{'='*50}\n")
    
    # Determine suite directory for loading baseline files
    if task.startswith("aspnetcore"):
        suite_dir = SUITES_DIR / "bench-aspnetcore"
    elif task.startswith("springboot"):
        suite_dir = SUITES_DIR / "bench-springboot"
    else:
        suite_dir = SUITES_DIR / "bench-fastapi"
    
    # Load prompt with model-specific customization and baseline files
    prompt = load_prompt(task, model, suite_dir)
    
    # Apply adaptive prompting if enabled
    if use_model_preferences and ADAPTIVE_PROMPTING_AVAILABLE:
        original_length = len(prompt)
        prompt = adapt_prompt_for_model(prompt, model, verbose=True)
        print(f"  Prompt adapted: {original_length} → {len(prompt)} chars\n")
    
    # Determine backends
    backend = determine_backend(model)
    refine_backend = determine_backend(refine_model)
    print(f"Using backend: {backend}")
    
    # Track all iterations
    iteration_results = []
    total_cost = 0.0
    total_tokens = 0
    current_max_tokens = 8192  # Start with 8K
    
    for iteration in range(1, iterations + 1):
        print(f"\n{'='*50}")
        print(f"ITERATION {iteration}/{iterations}")
        print(f"{'='*50}\n")
        
        # Determine which model to use
        if iteration == 1:
            current_model = model
            current_backend = backend
            current_prompt = prompt
        else:
            # For entropy analysis (force_iterations), use identical prompt every time
            if force_iterations:
                current_model = model  # Always use primary model
                current_backend = backend
                current_prompt = prompt  # Identical prompt for variance measurement
                print(f"Using identical prompt (entropy analysis mode)")
            else:
                # Check if previous iteration improved or got worse
                prev = iteration_results[-1]
                if iteration > 2:
                    prev_prev = iteration_results[-2]
                    # If refinement model made it worse, fall back to primary
                    if (prev['metrics'].get('tests_failed', 999) > prev_prev['metrics'].get('tests_failed', 999)):
                        current_model = model
                        current_backend = backend
                        print(f"⚠️  Refinement model made it worse, falling back to primary model")
                    else:
                        current_model = refine_model
                        current_backend = refine_backend
                else:
                    current_model = refine_model
                    current_backend = refine_backend
                
                # Build refinement prompt with detailed error feedback
                current_prompt = build_refinement_prompt(prompt, iteration_results[-1], output_dir, iteration-1)
        
        print(f"Using model: {current_model}")
        
        # Call model via unified LLM client
        if dry_run:
            print("DRY RUN - would call model here")
            raw_output = "DRY RUN"
            usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0, "stop_reason": "stop", "truncated": False}
        else:
            raw_output, usage = call_llm(
                current_model, current_prompt,
                max_tokens=current_max_tokens,
                temperature=temperature,
            )
        
        # Check for truncation and increase max_tokens for next iteration
        was_truncated = usage.get("truncated", False)
        if was_truncated:
            old_max = current_max_tokens
            current_max_tokens = min(current_max_tokens * 2, 32768)  # Double up to 32K max
            print(f"\n⚠️  Detected truncation! Increasing max_tokens: {old_max} -> {current_max_tokens}")
        
        total_cost += usage["estimated_cost_usd"]
        total_tokens += usage["total_tokens"]
        
        # Save iteration output
        iter_output_file = output_dir / f"raw_output_iter{iteration}.txt"
        iter_output_file.write_text(raw_output)
        print(f"Saved iteration {iteration} output ({len(raw_output)} chars)")
        
        # Create workspace for this iteration - determine suite from task
        if task.startswith("aspnetcore"):
            suite_dir = SUITES_DIR / "bench-aspnetcore"
        elif task.startswith("springboot"):
            suite_dir = SUITES_DIR / "bench-springboot"
        else:
            suite_dir = SUITES_DIR / "bench-fastapi"
        
        workspace = output_dir / f"workspace_iter{iteration}"
        shutil.copytree(suite_dir, workspace)
        print(f"Created workspace: {workspace}")
        
        # Extract files and generate diff using git
        files_applied, apply_message, diff = extract_and_apply_files(raw_output, workspace)
        
        if files_applied and diff:
            iter_diff_file = output_dir / f"changes_iter{iteration}.diff"
            iter_diff_file.write_text(diff)
            print(f"Generated diff ({len(diff.splitlines())} lines)")
            print(f"Apply: {apply_message}")
        else:
            print(f"WARNING: {apply_message}")
            diff = None
        
        # Results for this iteration
        iter_result = {
            "iteration": iteration,
            "model": current_model,
            "max_tokens_used": current_max_tokens if not dry_run else 8192,
            "was_truncated": was_truncated if not dry_run else False,
            "gates": {
                "diff_extracted": diff is not None,
                "diff_applied": files_applied,
                "tests_passed": False,
                "mypy_passed": False,
                "ruff_passed": False,
            },
            "metrics": {
                "output_length": len(raw_output),
                "diff_lines": len(diff.splitlines()) if diff else 0,
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
                "total_tokens": usage["total_tokens"],
                "estimated_cost_usd": usage["estimated_cost_usd"],
            },
        }
        
        # Run tests if files were applied successfully
        if files_applied and not dry_run:
            iter_result["apply_message"] = apply_message
            
            # Run tests with task_id
            test_results = run_tests(workspace, task)
            iter_result["gates"]["tests_passed"] = test_results["tests_passed"]
            iter_result["gates"]["mypy_passed"] = test_results["mypy_passed"]
            iter_result["gates"]["ruff_passed"] = test_results["ruff_passed"]
            iter_result["metrics"].update({
                "tests_total": test_results["tests_total"],
                "tests_failed": test_results["tests_failed"],
                "mypy_errors": test_results["mypy_errors"],
                "ruff_errors": test_results["ruff_errors"],
            })
            
            # Save detailed outputs
            (output_dir / f"pytest_iter{iteration}.txt").write_text(test_results.get("pytest_output", ""))
            (output_dir / f"mypy_iter{iteration}.txt").write_text(test_results.get("mypy_output", ""))
            (output_dir / f"ruff_iter{iteration}.txt").write_text(test_results.get("ruff_output", ""))
            
            # Check if all gates passed
            if all(iter_result["gates"].values()):
                print(f"\n✓ All gates passed on iteration {iteration}!")
                # Only break early if not forcing all iterations (for entropy analysis)
                if not force_iterations:
                    iteration_results.append(iter_result)
                    break
                else:
                    if iteration < iterations:
                        print(f"  Continuing to iteration {iteration + 1} (--force-iterations enabled)")
        
        iteration_results.append(iter_result)
    
    # Final results (use last iteration or best iteration)
    final_result = iteration_results[-1]
    results = {
        "model": model,
        "backend": backend,
        "task": task,
        "timestamp": timestamp,
        "iterations": len(iteration_results),
        "gates": final_result["gates"],
        "metrics": {
            **final_result["metrics"],
            "total_cost_usd": total_cost,
            "total_tokens": total_tokens,
        },
        "iteration_history": iteration_results,
    }
    
    # Save summary
    (output_dir / "summary.json").write_text(json.dumps(results, indent=2))
    
    # Print summary
    print(f"\n{'='*50}")
    print("RESULTS")
    print(f"{'='*50}")
    print(f"Iterations:     {len(iteration_results)}/{iterations}")
    print(f"Diff Extracted: {results['gates']['diff_extracted']}")
    print(f"Diff Applied:   {results['gates']['diff_applied']}")
    print(f"Tests Passed:   {results['gates']['tests_passed']}")
    print(f"Types Passed:   {results['gates']['mypy_passed']}")
    print(f"Lint Passed:    {results['gates']['ruff_passed']}")
    if results['metrics']['total_cost_usd'] > 0:
        print(f"\nTotal Cost:     ${results['metrics']['total_cost_usd']:.4f}")
        print(f"Total Tokens:   {results['metrics']['total_tokens']:,}")
    print(f"\nResults saved to: {output_dir}")
    
    return results


def build_refinement_prompt(original_prompt: str, previous_result: dict, output_dir: Path, prev_iteration: int) -> str:
    """Build a refinement prompt based on previous iteration's failures with detailed error messages."""
    
    error_details = []
    
    if not previous_result["gates"]["diff_applied"]:
        error_details.append(f"\n## FILE EXTRACTION ERROR\n{previous_result.get('apply_message', 'unknown error')}")
    
    if not previous_result["gates"]["tests_passed"]:
        pytest_file = output_dir / f"pytest_iter{prev_iteration}.txt"
        if pytest_file.exists():
            pytest_output = pytest_file.read_text()
            # Extract first 30 lines of errors
            error_lines = [l for l in pytest_output.split('\n') if 'ERROR' in l or 'FAILED' in l or 'SyntaxError' in l or 'ImportError' in l][:30]
            error_details.append(f"\n## TEST FAILURES\n" + '\n'.join(error_lines[:20]))
    
    if not previous_result["gates"]["mypy_passed"]:
        mypy_file = output_dir / f"mypy_iter{prev_iteration}.txt"
        if mypy_file.exists():
            mypy_output = mypy_file.read_text()
            # Extract first 20 lines of errors
            error_lines = [l for l in mypy_output.split('\n') if 'error:' in l][:20]
            if error_lines:
                error_details.append(f"\n## TYPE CHECK ERRORS\n" + '\n'.join(error_lines))
    
    if not previous_result["gates"]["ruff_passed"]:
        ruff_file = output_dir / f"ruff_iter{prev_iteration}.txt"
        if ruff_file.exists():
            ruff_output = ruff_file.read_text()
            # Extract first 15 lines of issues
            error_lines = ruff_output.split('\n')[:15]
            if error_lines:
                error_details.append(f"\n## LINT ISSUES (first 15)\n" + '\n'.join(error_lines))
    
    refinement = f"""Your previous attempt (iteration {prev_iteration}) had errors. Here are the specific issues:

{''.join(error_details)}

---

Please provide CORRECTED file contents that fix ALL of these issues.

Use the same FILE: block format:

```
FILE: path/to/file.py
---
<complete corrected file contents>
---
```

CRITICAL REQUIREMENTS:
1. Fix the SPECIFIC errors shown above
2. Provide COMPLETE file contents for each file (no truncation)
3. Ensure all imports are correct and all methods exist
4. Code must be syntactically valid Python
5. Address type checking and linting issues

Original task for reference:
{original_prompt}

Provide your CORRECTED files:
"""
    
    return refinement
    """Run a single benchmark trial."""
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    model_safe = model.replace(":", "-").replace("/", "-")
    output_dir = RESULTS_DIR / f"{timestamp}-{model_safe}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n{'='*50}")
    print(f"Benchmark: {task}")
    print(f"Model: {model}")
    print(f"Output: {output_dir}")
    print(f"{'='*50}\n")
    
    # Load prompt
    prompt = load_prompt(task)
    
    # Determine backend and call model
    backend = determine_backend(model)
    print(f"Using backend: {backend}")
    
    if dry_run:
        print("DRY RUN - would call model here")
        raw_output = "DRY RUN"
        usage = {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0, "estimated_cost_usd": 0.0}
    else:
        if backend == "openai":
            raw_output, usage = call_openai(model, prompt)
        elif backend == "anthropic":
            raw_output, usage = call_anthropic(model, prompt)
        else:
            raw_output, usage = call_ollama(model, prompt)
    
    # Save raw output
    (output_dir / "raw_output.txt").write_text(raw_output)
    print(f"Saved raw output ({len(raw_output)} chars)")
    
    # Extract diff
    diff = extract_diff(raw_output)
    if diff:
        (output_dir / "changes.diff").write_text(diff)
        print(f"Extracted diff ({len(diff.splitlines())} lines)")
    else:
        print("WARNING: Could not extract diff from output")
    
    # Create workspace
    suite_dir = SUITES_DIR / "bench-fastapi"
    workspace = output_dir / "workspace"
    shutil.copytree(suite_dir, workspace)
    print(f"Created workspace: {workspace}")
    
    # Results structure
    results = {
        "model": model,
        "backend": backend,
        "task": task,
        "timestamp": timestamp,
        "gates": {
            "diff_extracted": diff is not None,
            "diff_applied": False,
            "tests_passed": False,
            "mypy_passed": False,
            "ruff_passed": False,
        },
        "metrics": {
            "output_length": len(raw_output),
            "diff_lines": len(diff.splitlines()) if diff else 0,
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
            "total_tokens": usage["total_tokens"],
            "estimated_cost_usd": usage["estimated_cost_usd"],
        },
    }
    
    # Apply diff if extracted
    if diff and not dry_run:
        applied, message = apply_diff(diff, workspace)
        results["gates"]["diff_applied"] = applied
        results["apply_message"] = message
        print(f"Diff application: {message}")
        
        if applied:
            # Run tests
            test_results = run_tests(workspace)
            results["gates"]["tests_passed"] = test_results["tests_passed"]
            results["gates"]["mypy_passed"] = test_results["mypy_passed"]
            results["gates"]["ruff_passed"] = test_results["ruff_passed"]
            results["metrics"].update({
                "tests_total": test_results["tests_total"],
                "tests_failed": test_results["tests_failed"],
                "mypy_errors": test_results["mypy_errors"],
                "ruff_errors": test_results["ruff_errors"],
            })
            
            # Save detailed outputs
            (output_dir / "pytest.txt").write_text(test_results.get("pytest_output", ""))
            (output_dir / "mypy.txt").write_text(test_results.get("mypy_output", ""))
            (output_dir / "ruff.txt").write_text(test_results.get("ruff_output", ""))
    
    # Save summary
    (output_dir / "summary.json").write_text(json.dumps(results, indent=2))
    
    # Print summary
    print(f"\n{'='*50}")
    print("RESULTS")
    print(f"{'='*50}")
    print(f"Diff Extracted: {results['gates']['diff_extracted']}")
    print(f"Diff Applied:   {results['gates']['diff_applied']}")
    print(f"Tests Passed:   {results['gates']['tests_passed']}")
    print(f"Types Passed:   {results['gates']['mypy_passed']}")
    print(f"Lint Passed:    {results['gates']['ruff_passed']}")
    if results['metrics']['estimated_cost_usd'] > 0:
        print(f"\nCost:           ${results['metrics']['estimated_cost_usd']:.4f}")
        print(f"Tokens:         {results['metrics']['total_tokens']:,} ({results['metrics']['input_tokens']:,} in, {results['metrics']['output_tokens']:,} out)")
    print(f"\nResults saved to: {output_dir}")
    
    return results


def run_with_entropy_control(
    model: str,
    task: str = "fastapi-001",
    dry_run: bool = False,
    refine_model: str = None,
    use_model_preferences: bool = False,
    min_confidence: float = 0.90,
    max_runs: int = 5,
    quality_variance_threshold: float = 0.15,
    temperature: float = 0.2,
) -> dict:
    """
    Run benchmark with automatic entropy control.
    
    Runs iterations until variance stabilizes or max runs reached.
    Returns aggregated results with confidence intervals.
    """
    if not ENTROPY_CONTROL_AVAILABLE:
        print("⚠️  entropy_control module not available, running single iteration")
        return run_benchmark(model, task, dry_run, 1, refine_model, False, use_model_preferences, temperature)
    
    controller = EntropyController(
        min_confidence=min_confidence,
        max_runs=max_runs,
        quality_variance_threshold=quality_variance_threshold,
    )
    
    print(f"\n{'='*70}")
    print(f"ENTROPY CONTROL ENABLED")
    print(f"{'='*70}")
    print(f"Min confidence: {min_confidence:.0%}")
    print(f"Max runs: {max_runs}")
    print(f"Quality variance threshold: {quality_variance_threshold:.3f}")
    print(f"Temperature: {temperature}")
    print(f"{'='*70}\n")
    
    results = []
    run_count = 0
    
    while controller.should_continue(results):
        run_count += 1
        print(f"\n{'#'*70}")
        print(f"ENTROPY RUN {run_count}/{max_runs}")
        print(f"{'#'*70}\n")
        
        # Run single iteration
        result = run_benchmark(
            model=model,
            task=task,
            dry_run=dry_run,
            iterations=1,
            refine_model=refine_model,
            force_iterations=False,
            use_model_preferences=use_model_preferences,
            temperature=temperature,
        )
        
        results.append(result)
        
        # Calculate current statistics
        stats = controller.get_statistics(results)
        
        print(f"\n{'-'*70}")
        print(f"ENTROPY STATISTICS (after {run_count} runs)")
        print(f"{'-'*70}")
        print(controller.format_statistics(stats))
        print(f"\nRecommendation: {controller.recommend_action(stats)}")
        print(f"{'-'*70}\n")
        
        if not controller.should_continue(results):
            break
    
    # Calculate final statistics
    final_stats = controller.get_statistics(results)
    
    # Create aggregated result
    aggregated = {
        'model': model,
        'task': task,
        'entropy_control': True,
        'runs': len(results),
        'individual_results': results,
        'statistics': final_stats,
        'gates': {
            gate: {
                'mean': final_stats['gate_variances'][gate]['mean'],
                'std': final_stats['gate_variances'][gate]['std'],
            }
            for gate in ['diff_extracted', 'diff_applied', 'tests_passed', 'mypy_passed', 'ruff_passed']
        },
        'confidence': final_stats['confidence'],
        'confidence_interval': final_stats['confidence_interval'],
    }
    
    print(f"\n{'='*70}")
    print(f"FINAL ENTROPY-CONTROLLED RESULTS")
    print(f"{'='*70}")
    print(controller.format_statistics(final_stats))
    print(f"\nRecommendation: {controller.recommend_action(final_stats)}")
    print(f"{'='*70}\n")
    
    return aggregated


def main():
    parser = argparse.ArgumentParser(description="Multi-backend LLM Benchmark Runner")
    parser.add_argument("--model", "-m", required=True, help="Model to use (e.g., gpt-4o, claude-sonnet, ollama:qwen2.5-coder:7b)")
    parser.add_argument("--task", "-t", default="fastapi-001", help="Task ID (default: fastapi-001)")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually call the model")
    parser.add_argument("--list-models", action="store_true", help="List available models")
    parser.add_argument("--iterations", "-i", type=int, default=1, help="Number of refinement iterations (default: 1)")
    parser.add_argument("--refine-with", default="ollama:qwen2.5-coder:7b", help="Model for refinement iterations (default: ollama:qwen2.5-coder:7b, use 'primary' for same as --model)")
    parser.add_argument("--force-iterations", action="store_true", help="Force all iterations to run (disable early exit on success, for entropy analysis)")
    parser.add_argument("--use-model-preferences", action="store_true", help="Adapt prompt based on model's stated preferences (experimental)")
    parser.add_argument("--entropy-control", action="store_true", help="Enable automatic entropy control (auto re-run on high variance)")
    parser.add_argument("--min-confidence", type=float, default=0.90, help="Minimum confidence level for entropy control (default: 0.90)")
    parser.add_argument("--max-entropy-runs", type=int, default=5, help="Maximum runs for entropy control (default: 5)")
    parser.add_argument("--variance-threshold", type=float, default=0.15, help="Quality variance threshold for entropy control (default: 0.15)")
    parser.add_argument("--temperature", type=float, default=0.2, help="Sampling temperature for all providers (default: 0.2)")
    
    args = parser.parse_args()
    
    if args.list_models:
        print("Available models:")
        print("\nOpenAI:")
        for name, model_id in OPENAI_MODELS.items():
            print(f"  {name} -> {model_id}")
        print("\nAnthropic:")
        for name, model_id in ANTHROPIC_MODELS.items():
            print(f"  {name} -> {model_id}")
        print("\nGemini (prefix with 'gemini:' or use bare model name):")
        for name, model_id in GEMINI_MODELS.items():
            pricing = GEMINI_PRICING.get(model_id, (0, 0))
            print(f"  gemini:{name} -> {model_id}  (${pricing[0]}/{pricing[1]} per 1M tok)")
        print("  Auth: GEMINI_API_KEY or VERTEX_AI_API_KEY + VERTEX_AI_PROJECT")
        print("\nOllama Cloud (prefix with 'cloud:'):")
        print("  cloud:qwen3-coder-next          # 80B MoE, 3B active — coding specialist")
        print("  cloud:deepseek-v3.2             # 671B MoE — DeepSeek flagship")
        print("  cloud:devstral-2                # 123B Mistral coding agent")
        print("  cloud:qwen3-coder:480b          # 480B MoE — largest Qwen coder")
        print("  See: https://ollama.com/search?c=cloud")
        print("\nOllama Local (prefix with 'ollama:'):")
        print("  ollama:qwen2.5-coder:32b        # Best open-source coder for 32GB")
        print("  ollama:qwen2.5-coder:14b")
        print("  ollama:qwen2.5-coder:7b")
        print("  ollama:devstral:24b")
        print("  ollama:<any-model>")
        return
    
    refine_model = args.model if args.refine_with == "primary" else args.refine_with
    
    # Check if entropy control is enabled
    if args.entropy_control:
        if args.iterations > 1:
            print("⚠️  Warning: --iterations ignored when --entropy-control is enabled")
        if args.force_iterations:
            print("⚠️  Warning: --force-iterations ignored when --entropy-control is enabled")
        
        run_with_entropy_control(
            model=args.model,
            task=args.task,
            dry_run=args.dry_run,
            refine_model=refine_model,
            use_model_preferences=args.use_model_preferences,
            min_confidence=args.min_confidence,
            max_runs=args.max_entropy_runs,
            quality_variance_threshold=args.variance_threshold,
            temperature=args.temperature,
        )
    else:
        run_benchmark(
            args.model, 
            args.task, 
            args.dry_run, 
            args.iterations, 
            refine_model, 
            args.force_iterations,
            args.use_model_preferences,
            args.temperature
        )


if __name__ == "__main__":
    main()
