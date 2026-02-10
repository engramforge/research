#!/usr/bin/env python3
"""LLM Judge pipeline for qualitative code evaluation.

Evaluates generated code against the quality rubric from Appendix G.2:
  - Clean Code Principles (SRP, naming, small functions, DRY, error handling)
  - Design Pattern Recognition (DI, Repository, DTO, Layered, Factory)
  - Framework Idiom Adherence (language-specific idiomatic usage)
  - Code Organization (file structure, imports, config separation)

Judge assignment is DATA-DRIVEN, informed by our pilot study findings:
  - Cross-family: never self-evaluate (Claude ≠ judge Claude, etc.)
  - Consistency-weighted: prefer judges with low σ and high structure Jaccard
  - Two judges: Gemini 3 Pro (σ=0.00, cheapest) and Claude Sonnet 4.5 (σ=0.26, most detail-oriented)

Modes:
  --calibrate    Judge 5 runs with BOTH judges, report inter-rater agreement
  --dry-run      Show what would be judged without calling APIs
  --resume       Skip already-judged runs (default)
  --force        Re-judge even if quality/llm_judge.json exists
  --limit N      Only judge N runs (for testing)

Reads:  pilot/results/{run_dir}/workspace_iter{N}/ (generated code)
        pilot/results/run_manifest.json (entropy-only filter)
Writes: pilot/results/{run_dir}/quality/llm_judge.json
        pilot/results/quality_analysis/judge_summary.json
"""

import argparse
import json
import os
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Optional

# Unified LLM client
from llm_client import call_llm, determine_backend


class BillingError(Exception):
    """Raised when the API returns a billing/credit-related error."""
    pass


PILOT_DIR = Path(__file__).resolve().parent
RESULTS_DIR = PILOT_DIR / "results"

# ──────────────────────────────────────────────────────────────────────
# Judge Assignment — data-driven from pilot findings (§5.4)
#
# Criteria for judge selection:
#   1. Different model family from code author (no self-evaluation)
#   2. High consistency (low σ) — judges must be deterministic
#   3. Notices detail (type annotations, docstrings, naming)
#   4. Cost-efficient for 165+ calls
#
# From our benchmark data:
#   - Gemini 3 Pro Preview: σ=0.00, perfect 5/5 all tasks, $0.022/run
#   - Claude Sonnet 4.5:    σ=0.26, 4.93/5 mean, Structure J=1.00, $0.073/run
#   - GPT-4o:               σ=0.00, 5.00 Java/C#, Structure J=0.78
#
# Assignment:
#   Claude output  → Gemini 3 Pro   (different family, cheapest, perfect consistency)
#   GPT output     → Claude Sonnet  (different family, most detail-oriented)
#   Gemini output  → Claude Sonnet  (different family, highest structure Jaccard)
#   Open-weight    → Gemini 3 Pro   (different family, cost-efficient)
# ──────────────────────────────────────────────────────────────────────

JUDGE_ASSIGNMENT = {
    "claude":         "gemini-3-pro-preview",   # Claude → Gemini 3 Pro
    "gpt":            "claude-sonnet-4.5",       # GPT → Claude Sonnet
    "gemini":         "claude-sonnet-4.5",       # Gemini → Claude Sonnet
    "cloud:qwen":     "gemini-3-pro-preview",   # Qwen → Gemini 3 Pro
    "cloud:deepseek": "gemini-3-pro-preview",   # DeepSeek → Gemini 3 Pro
}

# For calibration: second judge for inter-rater reliability
CALIBRATION_JUDGE_ASSIGNMENT = {
    "claude":         "claude-sonnet-4.5",       # Claude → alt judge: Claude Sonnet
    "gpt":            "gemini-3-pro-preview",    # GPT → alt judge: Gemini
    "gemini":         "gemini-3-pro-preview",    # Gemini → alt judge: Gemini (actually gpt would be better but costly)
    "cloud:qwen":     "claude-sonnet-4.5",       # Qwen → alt: Claude
    "cloud:deepseek": "claude-sonnet-4.5",       # DeepSeek → alt: Claude
}


# ──────────────────────────────────────────────────────────────────────
# Judge prompt templates
# ──────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior software engineer conducting a rigorous code review.
You evaluate generated code against established quality criteria.
You must provide specific line references and code snippets for every score.
You are evaluating {language}/{framework} code.

IMPORTANT:
- Score based on what IS present in the code, not what you think should have been generated.
- A minimal but clean solution scores higher than an elaborate but messy one.
- Be consistent: the same quality of code should always receive the same score.
- Respond ONLY with valid JSON matching the schema provided. No markdown fences."""

CLEAN_CODE_RUBRIC = """## Clean Code Evaluation (Robert C. Martin)

Score each dimension 1-5 with a mandatory justification citing specific code.

1. **Single Responsibility**: Does each class/function do one thing?
   1=god class, 3=mostly separated, 5=pristine SRP
   
2. **Meaningful Names**: Are variable/function/class names self-documenting?
   1=x, data, temp; 3=adequate; 5=reads like prose
   
3. **Small Functions**: Are functions short and focused?
   1=>50 lines avg, 3=15-25 lines, 5=<10 lines
   
4. **DRY (Don't Repeat Yourself)**: Is logic duplicated?
   1=copy-paste everywhere, 3=some duplication, 5=properly abstracted
   
5. **Error Handling**: Are errors handled at appropriate levels with meaningful messages?
   1=bare except/catch-all, 3=typed exceptions, 5=domain-specific error hierarchy"""

DESIGN_PATTERN_RUBRIC = """## Design Pattern Recognition

For each pattern, classify as:
- PRESENT_CORRECT: Pattern used appropriately
- PRESENT_MISAPPLIED: Pattern used but incorrectly or unnecessarily
- ABSENT_EXPECTED: Pattern should be here but isn't
- ABSENT_ACCEPTABLE: Pattern not present and not needed

Patterns to evaluate:
- Dependency Injection
- Repository Pattern
- DTO (Data Transfer Object) Pattern
- Layered Architecture (Controller-Service-Repository)
- Factory / Builder (if applicable)"""

IDIOM_RUBRICS = {
    "python": """## Python/FastAPI Idiom Adherence

For each idiom, classify as IDIOMATIC / FUNCTIONAL_NOT_IDIOMATIC / ANTI_PATTERN:
- async/await usage (vs synchronous where async is expected)
- Pydantic model usage for request/response schemas
- Dependency injection via Depends()
- Router organization (APIRouter vs monolithic app)
- HTTPException usage vs bare raises
- Path operation decorator patterns
- Type hints on function signatures""",

    "csharp": """## C#/ASP.NET Core Idiom Adherence

For each idiom, classify as IDIOMATIC / FUNCTIONAL_NOT_IDIOMATIC / ANTI_PATTERN:
- IServiceCollection DI registration
- Controller inheritance (ControllerBase vs Controller)
- ActionResult<T> return types vs bare types
- [ApiController] attribute usage
- Constructor injection for dependencies
- Async/await patterns
- Nullable reference types""",

    "java": """## Java/Spring Boot Idiom Adherence

For each idiom, classify as IDIOMATIC / FUNCTIONAL_NOT_IDIOMATIC / ANTI_PATTERN:
- @RestController vs @Controller + @ResponseBody
- Constructor injection vs @Autowired field injection
- ResponseEntity<T> usage
- @Valid annotation for request validation
- Service layer @Service annotation
- Spring Data repository interfaces
- Lombok usage (if present)""",
}

OUTPUT_SCHEMA = """{
  "clean_code": {
    "single_responsibility": {"score": <1-5>, "justification": "<specific code refs>"},
    "meaningful_names": {"score": <1-5>, "justification": "<specific code refs>"},
    "small_functions": {"score": <1-5>, "justification": "<specific code refs>"},
    "dry": {"score": <1-5>, "justification": "<specific code refs>"},
    "error_handling": {"score": <1-5>, "justification": "<specific code refs>"}
  },
  "design_patterns": [
    {"pattern": "<name>", "status": "<classification>", "evidence": "<code ref>"}
  ],
  "idiom_adherence": [
    {"idiom": "<name>", "status": "<classification>", "evidence": "<code ref>"}
  ],
  "organization": {
    "file_structure": {"score": <1-5>, "justification": "<explanation>"},
    "config_separation": {"score": <1-5>, "justification": "<explanation>"}
  }
}"""


# ──────────────────────────────────────────────────────────────────────
# Helper functions
# ──────────────────────────────────────────────────────────────────────

def detect_language(task: str) -> tuple[str, str]:
    """Return (language, framework) for a task ID."""
    if "fastapi" in task:
        return "python", "fastapi"
    elif "aspnetcore" in task:
        return "csharp", "aspnetcore"
    elif "springboot" in task:
        return "java", "springboot"
    return "unknown", "unknown"


def select_judge_model(model_under_test: str, calibration: bool = False) -> str:
    """Select judge model, avoiding self-evaluation bias.

    Uses data-driven assignment from pilot study findings.
    If calibration=True, returns the alternate judge for inter-rater testing.
    """
    table = CALIBRATION_JUDGE_ASSIGNMENT if calibration else JUDGE_ASSIGNMENT
    for prefix, judge in table.items():
        if model_under_test.startswith(prefix):
            return judge
    # Default: gemini for cost efficiency
    return "gemini-3-pro-preview"


def collect_source_code(workspace_dir: Path, language: str) -> str:
    """Collect all relevant source files into a single string for the judge."""
    if language == "python":
        app_dir = workspace_dir / "app"
        if not app_dir.exists():
            return ""
        files = sorted(app_dir.rglob("*.py"))
        files = [f for f in files if "__pycache__" not in str(f)]
    elif language == "csharp":
        src_dir = workspace_dir / "src" / "BenchApi"
        if not src_dir.exists():
            return ""
        files = sorted(src_dir.rglob("*.cs"))
        files = [f for f in files if "obj" not in str(f) and "bin" not in str(f)]
    elif language == "java":
        src_dir = workspace_dir / "src" / "main" / "java"
        if not src_dir.exists():
            return ""
        files = sorted(src_dir.rglob("*.java"))
        files = [f for f in files if "target" not in str(f)]
    else:
        return ""

    parts = []
    for f in files:
        rel = f.relative_to(workspace_dir)
        content = f.read_text(encoding="utf-8", errors="replace")
        parts.append(f"### {rel}\n```\n{content}\n```")

    return "\n\n".join(parts)


def build_judge_prompt(code: str, language: str, framework: str, task_desc: str = "") -> str:
    """Build the full judge evaluation prompt."""
    idiom_rubric = IDIOM_RUBRICS.get(language, "")
    default_desc = "Add an orders endpoint to an existing REST API with proper models, service layer, and tests."

    return f"""## Code Under Review

{code}

## Task Description
{task_desc or default_desc}

## Evaluation Criteria

{CLEAN_CODE_RUBRIC}

{DESIGN_PATTERN_RUBRIC}

{idiom_rubric}

## Required Output Format

Respond with ONLY the following JSON structure (no markdown fences, no explanation outside JSON):

{OUTPUT_SCHEMA}"""


def parse_judge_response(raw: str) -> Optional[dict]:
    """Parse JSON from judge response, with recovery for common issues."""
    # Strip markdown code fences if present
    cleaned = raw.strip()
    cleaned = re.sub(r'^```(?:json)?\s*\n?', '', cleaned)
    cleaned = re.sub(r'\n?```\s*$', '', cleaned)
    cleaned = cleaned.strip()

    # Try direct parse
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Try to find JSON object in the response
    match = re.search(r'\{[\s\S]*\}', cleaned)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            pass

    # Try fixing common issues: trailing commas, single quotes
    try:
        fixed = re.sub(r',\s*([}\]])', r'\1', cleaned)
        fixed = fixed.replace("'", '"')
        return json.loads(fixed)
    except json.JSONDecodeError:
        pass

    return None


def validate_judge_result(result: dict) -> tuple[bool, str]:
    """Validate that the judge result has the expected structure."""
    if "clean_code" not in result:
        return False, "missing 'clean_code'"

    cc = result["clean_code"]
    required_dims = ["single_responsibility", "meaningful_names", "small_functions", "dry", "error_handling"]
    for dim in required_dims:
        if dim not in cc:
            return False, f"missing clean_code.{dim}"
        if "score" not in cc[dim]:
            return False, f"missing clean_code.{dim}.score"
        score = cc[dim]["score"]
        if not isinstance(score, (int, float)) or score < 1 or score > 5:
            return False, f"invalid clean_code.{dim}.score: {score}"

    if "design_patterns" not in result:
        return False, "missing 'design_patterns'"
    if "idiom_adherence" not in result:
        return False, "missing 'idiom_adherence'"
    if "organization" not in result:
        return False, "missing 'organization'"

    return True, "ok"


def compute_composite_scores(judge_result: dict) -> dict[str, float]:
    """Compute composite quality scores from LLM judge output."""
    # Clean code index: mean of 5 dimensions (all scored 1-5)
    cc = judge_result.get("clean_code", {})
    cc_scores = [
        cc.get("single_responsibility", {}).get("score", 0),
        cc.get("meaningful_names", {}).get("score", 0),
        cc.get("small_functions", {}).get("score", 0),
        cc.get("dry", {}).get("score", 0),
        cc.get("error_handling", {}).get("score", 0),
    ]
    valid_cc = [s for s in cc_scores if s > 0]
    clean_code_index = sum(valid_cc) / max(len(valid_cc), 1)

    # Pattern appropriateness: fraction of PRESENT_CORRECT + ABSENT_ACCEPTABLE
    patterns = judge_result.get("design_patterns", [])
    good_patterns = sum(
        1 for p in patterns
        if p.get("status") in ("PRESENT_CORRECT", "ABSENT_ACCEPTABLE")
    )
    pattern_score = good_patterns / max(len(patterns), 1)

    # Idiom score: fraction of IDIOMATIC
    idioms = judge_result.get("idiom_adherence", [])
    idiomatic = sum(1 for i in idioms if i.get("status") == "IDIOMATIC")
    idiom_score = idiomatic / max(len(idioms), 1)

    # Organization: mean of sub-scores (1-5 scale)
    org = judge_result.get("organization", {})
    org_scores = [
        org.get("file_structure", {}).get("score", 0),
        org.get("config_separation", {}).get("score", 0),
    ]
    valid_org = [s for s in org_scores if s > 0]
    org_score = sum(valid_org) / max(len(valid_org), 1)

    # Overall: weighted composite (everything on 0-5 scale)
    overall = (
        clean_code_index * 0.35
        + pattern_score * 5 * 0.25    # scale 0-1 → 0-5
        + idiom_score * 5 * 0.25      # scale 0-1 → 0-5
        + org_score * 0.15
    )

    return {
        "clean_code_index": round(clean_code_index, 2),
        "pattern_appropriateness": round(pattern_score, 2),
        "idiom_score": round(idiom_score, 2),
        "organization_score": round(org_score, 2),
        "overall_quality": round(overall, 2),
    }


# ──────────────────────────────────────────────────────────────────────
# Judge a single run
# ──────────────────────────────────────────────────────────────────────

def judge_single_run(
    run_dir: Path,
    judge_model: str,
    *,
    max_retries: int = 2,
    verbose: bool = True,
) -> Optional[dict]:
    """Judge a single benchmark run.

    Returns the full judge result dict, or None on failure.
    """
    summary = json.load(open(run_dir / "summary.json"))
    model = summary.get("model", "unknown")
    task = summary.get("task", "unknown")
    lang, framework = detect_language(task)
    iterations = summary.get("iterations", 1)

    # Find workspace
    workspace = run_dir / f"workspace_iter{iterations}"
    if not workspace.exists():
        workspace = run_dir / "workspace_iter1"
    if not workspace.exists():
        if verbose:
            print(f"  ⚠️  No workspace found for {run_dir.name}")
        return None

    # Collect source code
    code = collect_source_code(workspace, lang)
    if not code:
        if verbose:
            print(f"  ⚠️  No source code found for {run_dir.name}")
        return None

    # Build prompts
    system = SYSTEM_PROMPT.format(language=lang, framework=framework)
    user_prompt = build_judge_prompt(code, lang, framework)

    if verbose:
        print(f"  Model under test: {model}")
        print(f"  Judge: {judge_model}")
        print(f"  Language: {lang}/{framework}")
        print(f"  Code: {len(code)} chars")

    # Call judge with retry
    for attempt in range(1, max_retries + 1):
        try:
            raw_response, usage = call_llm(
                judge_model,
                user_prompt,
                system_prompt=system,
                max_tokens=8192,
                temperature=0.0,   # deterministic judging
                verbose=verbose,
            )

            # Parse JSON
            parsed = parse_judge_response(raw_response)
            if parsed is None:
                if attempt < max_retries:
                    if verbose:
                        print(f"  ⚠️  JSON parse failed (attempt {attempt}), retrying...")
                    continue
                else:
                    if verbose:
                        print(f"  ✗  JSON parse failed after {max_retries} attempts")
                    # Save raw response for debugging
                    debug_dir = run_dir / "quality"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    (debug_dir / "llm_judge_raw.txt").write_text(raw_response)
                    return None

            # Validate structure
            valid, reason = validate_judge_result(parsed)
            if not valid:
                if attempt < max_retries:
                    if verbose:
                        print(f"  ⚠️  Invalid structure ({reason}), retrying...")
                    continue
                else:
                    if verbose:
                        print(f"  ✗  Invalid structure after {max_retries} attempts: {reason}")
                    debug_dir = run_dir / "quality"
                    debug_dir.mkdir(parents=True, exist_ok=True)
                    (debug_dir / "llm_judge_raw.txt").write_text(raw_response)
                    return None

            # Compute composite scores
            composites = compute_composite_scores(parsed)

            result = {
                "judge_model": judge_model,
                "model_under_test": model,
                "task": task,
                "language": lang,
                "framework": framework,
                "timestamp": time.strftime("%Y%m%dT%H%M%S"),
                "raw_scores": parsed,
                "composite_scores": composites,
                "judge_usage": usage,
                "code_chars": len(code),
            }

            if verbose:
                print(f"  ✓  Quality: {composites['overall_quality']:.2f}/5.00")
                print(f"     Clean code: {composites['clean_code_index']:.2f}, "
                      f"Patterns: {composites['pattern_appropriateness']:.0%}, "
                      f"Idioms: {composites['idiom_score']:.0%}, "
                      f"Org: {composites['organization_score']:.2f}")

            return result

        except Exception as e:
            err_str = str(e).lower()
            # Immediately bail on billing / credit errors — no point retrying
            if "credit balance" in err_str or "billing" in err_str or "quota" in err_str:
                if verbose:
                    print(f"  ✗  BILLING ERROR: {e}")
                raise BillingError(str(e)) from e
            if attempt < max_retries:
                if verbose:
                    print(f"  ⚠️  Error (attempt {attempt}): {e}")
                time.sleep(5)
            else:
                if verbose:
                    print(f"  ✗  Failed after {max_retries} attempts: {e}")
                return None

    return None


# ──────────────────────────────────────────────────────────────────────
# Calibration: inter-rater reliability
# ──────────────────────────────────────────────────────────────────────

def run_calibration(runs: list[str], n: int = 5) -> dict:
    """Judge n runs with BOTH judges and compute inter-rater agreement.

    Returns calibration report with per-dimension agreement stats.
    """
    print(f"\n{'='*60}")
    print(f"CALIBRATION MODE: Judging {n} runs with both judges")
    print(f"{'='*60}\n")

    # Pick n runs spanning different models/languages
    calibration_runs = _select_diverse_calibration_runs(runs, n)
    results = []

    for i, run_name in enumerate(calibration_runs, 1):
        run_dir = RESULTS_DIR / run_name
        summary = json.load(open(run_dir / "summary.json"))
        model = summary.get("model", "unknown")
        task = summary.get("task", "unknown")

        print(f"\n[{i}/{n}] {run_name}")
        print(f"  Model: {model}, Task: {task}")

        # Primary judge
        judge1 = select_judge_model(model, calibration=False)
        print(f"\n  --- Primary Judge: {judge1} ---")
        r1 = judge_single_run(run_dir, judge1)

        # Alternate judge
        judge2 = select_judge_model(model, calibration=True)
        # Avoid using same judge twice
        if judge2 == judge1:
            judge2 = "gpt-4o"
        print(f"\n  --- Alternate Judge: {judge2} ---")
        r2 = judge_single_run(run_dir, judge2)

        if r1 and r2:
            results.append({
                "run": run_name,
                "model": model,
                "task": task,
                "judge1": {"model": judge1, "scores": r1["composite_scores"], "raw": r1["raw_scores"]},
                "judge2": {"model": judge2, "scores": r2["composite_scores"], "raw": r2["raw_scores"]},
            })

    # Compute agreement metrics
    agreement = _compute_agreement(results)

    # Save calibration report
    report = {
        "timestamp": time.strftime("%Y%m%dT%H%M%S"),
        "n_runs": len(results),
        "results": results,
        "agreement": agreement,
    }

    cal_dir = RESULTS_DIR / "quality_analysis"
    cal_dir.mkdir(parents=True, exist_ok=True)
    with open(cal_dir / "calibration_report.json", "w") as f:
        json.dump(report, f, indent=2)

    # Print summary
    print(f"\n{'='*60}")
    print(f"CALIBRATION RESULTS ({len(results)} runs)")
    print(f"{'='*60}")
    for dim, stats in agreement.items():
        print(f"  {dim:30s}  MAD={stats['mad']:.2f}  corr={stats.get('correlation', 'n/a')}")
    print(f"\n  Saved to: {cal_dir / 'calibration_report.json'}")

    return report


def _select_diverse_calibration_runs(runs: list[str], n: int) -> list[str]:
    """Pick n runs spanning different models and languages."""
    by_lang = defaultdict(list)
    for run_name in runs:
        try:
            s = json.load(open(RESULTS_DIR / run_name / "summary.json"))
            task = s.get("task", "unknown")
            lang, _ = detect_language(task)
            by_lang[lang].append(run_name)
        except Exception:
            continue

    selected = []
    # Round-robin across languages
    langs = list(by_lang.keys())
    idx = {lang: 0 for lang in langs}
    while len(selected) < n and any(idx[l] < len(by_lang[l]) for l in langs):
        for lang in langs:
            if len(selected) >= n:
                break
            if idx[lang] < len(by_lang[lang]):
                selected.append(by_lang[lang][idx[lang]])
                idx[lang] += 1

    return selected[:n]


def _compute_agreement(results: list[dict]) -> dict:
    """Compute inter-rater agreement across calibration results."""
    if not results:
        return {}

    dimensions = ["clean_code_index", "pattern_appropriateness", "idiom_score",
                   "organization_score", "overall_quality"]

    agreement = {}
    for dim in dimensions:
        diffs = []
        pairs = []
        for r in results:
            s1 = r["judge1"]["scores"].get(dim, 0)
            s2 = r["judge2"]["scores"].get(dim, 0)
            diffs.append(abs(s1 - s2))
            pairs.append((s1, s2))

        mad = sum(diffs) / len(diffs) if diffs else 0

        # Pearson correlation (if enough data)
        corr = "n/a"
        if len(pairs) >= 3:
            x = [p[0] for p in pairs]
            y = [p[1] for p in pairs]
            mx, my = sum(x) / len(x), sum(y) / len(y)
            num = sum((xi - mx) * (yi - my) for xi, yi in pairs)
            dx = sum((xi - mx) ** 2 for xi in x) ** 0.5
            dy = sum((yi - my) ** 2 for yi in y) ** 0.5
            if dx > 0 and dy > 0:
                corr = round(num / (dx * dy), 3)

        agreement[dim] = {"mad": round(mad, 3), "correlation": corr, "n": len(diffs)}

    return agreement


# ──────────────────────────────────────────────────────────────────────
# Full pipeline
# ──────────────────────────────────────────────────────────────────────

def run_full_pipeline(
    runs: list[str],
    *,
    force: bool = False,
    limit: Optional[int] = None,
    verbose: bool = True,
) -> dict:
    """Judge all runs. Returns summary stats."""
    # Determine which need judging
    needs_judging = []
    already_done = 0
    for run_name in runs:
        judge_file = RESULTS_DIR / run_name / "quality" / "llm_judge.json"
        if judge_file.exists() and not force:
            already_done += 1
        else:
            needs_judging.append(run_name)

    if limit:
        needs_judging = needs_judging[:limit]

    print(f"\nLLM Judge Pipeline")
    print(f"  Total entropy runs:  {len(runs)}")
    print(f"  Already judged:      {already_done}")
    print(f"  To judge this run:   {len(needs_judging)}")

    if not needs_judging:
        print("  Nothing to do!")
        return {"judged": 0, "skipped": already_done}

    # Estimate cost
    # Rough: ~$0.015 per Gemini 3 Pro call, ~$0.07 per Claude Sonnet call
    gemini_count = sum(1 for r in needs_judging
                       if _run_uses_judge(r, "gemini-3-pro-preview"))
    claude_count = len(needs_judging) - gemini_count
    est_cost = gemini_count * 0.015 + claude_count * 0.07
    print(f"  Estimated cost:      ~${est_cost:.2f}")
    print(f"    Gemini 3 Pro:      {gemini_count} calls")
    print(f"    Claude Sonnet 4.5: {claude_count} calls")
    print()

    # Process runs
    successes = 0
    failures = 0
    consecutive_failures = 0
    max_consecutive_failures = 5  # circuit breaker
    total_cost = 0.0
    all_scores = []

    for i, run_name in enumerate(needs_judging, 1):
        run_dir = RESULTS_DIR / run_name
        summary = json.load(open(run_dir / "summary.json"))
        model = summary.get("model", "unknown")

        judge = select_judge_model(model)

        print(f"\n[{i}/{len(needs_judging)}] {run_name}")
        try:
            result = judge_single_run(run_dir, judge, verbose=verbose)
        except BillingError as e:
            print(f"\n🛑 BILLING ERROR — stopping pipeline to avoid wasting calls.")
            print(f"   {e}")
            failures += 1
            break

        if result:
            # Save result
            quality_dir = run_dir / "quality"
            quality_dir.mkdir(parents=True, exist_ok=True)
            with open(quality_dir / "llm_judge.json", "w") as f:
                json.dump(result, f, indent=2)

            successes += 1
            consecutive_failures = 0
            total_cost += result["judge_usage"].get("estimated_cost_usd", 0)
            all_scores.append({
                "run": run_name,
                "model": model,
                "task": summary.get("task"),
                "gates": summary.get("gates", {}),
                **result["composite_scores"],
            })
        else:
            failures += 1
            consecutive_failures += 1
            if consecutive_failures >= max_consecutive_failures:
                print(f"\n🛑 {max_consecutive_failures} consecutive failures — stopping pipeline.")
                break

    # Save aggregate summary
    _save_summary(all_scores, successes, failures, total_cost)

    print(f"\n{'='*60}")
    print(f"JUDGE PIPELINE COMPLETE")
    print(f"  Judged:   {successes}")
    print(f"  Failed:   {failures}")
    print(f"  Cost:     ${total_cost:.4f}")
    print(f"{'='*60}")

    return {"judged": successes, "failed": failures, "cost": total_cost}


def _run_uses_judge(run_name: str, expected_judge: str) -> bool:
    """Check if a run would use a specific judge model."""
    try:
        s = json.load(open(RESULTS_DIR / run_name / "summary.json"))
        judge = select_judge_model(s.get("model", ""))
        return judge == expected_judge
    except Exception:
        return False


def _save_summary(all_scores: list[dict], successes: int, failures: int, total_cost: float):
    """Save aggregate judge summary to quality_analysis/."""
    if not all_scores:
        return

    summary_dir = RESULTS_DIR / "quality_analysis"
    summary_dir.mkdir(parents=True, exist_ok=True)

    # Group by model
    by_model = defaultdict(list)
    for s in all_scores:
        by_model[s["model"]].append(s)

    model_summaries = {}
    for model, scores in sorted(by_model.items()):
        n = len(scores)
        dims = ["clean_code_index", "pattern_appropriateness", "idiom_score",
                "organization_score", "overall_quality"]
        model_summaries[model] = {
            "n": n,
            **{dim: round(sum(s[dim] for s in scores) / n, 3) for dim in dims},
        }

    summary = {
        "timestamp": time.strftime("%Y%m%dT%H%M%S"),
        "total_judged": successes,
        "total_failed": failures,
        "total_cost_usd": round(total_cost, 4),
        "by_model": model_summaries,
        "all_scores": all_scores,
    }

    with open(summary_dir / "judge_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n  Summary saved to: {summary_dir / 'judge_summary.json'}")

    # Print model leaderboard
    print(f"\n  Quality Leaderboard (by overall_quality):")
    for model, stats in sorted(model_summaries.items(), key=lambda x: -x[1]["overall_quality"]):
        print(f"    {model:35s}  {stats['overall_quality']:.2f}/5  "
              f"(cc={stats['clean_code_index']:.2f} pat={stats['pattern_appropriateness']:.0%} "
              f"idiom={stats['idiom_score']:.0%} org={stats['organization_score']:.2f})  n={stats['n']}")


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="LLM Judge: qualitative code evaluation")
    parser.add_argument("--calibrate", action="store_true",
                        help="Run calibration (5 runs with both judges)")
    parser.add_argument("--calibrate-n", type=int, default=5,
                        help="Number of calibration runs (default: 5)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show what would be judged without calling APIs")
    parser.add_argument("--force", action="store_true",
                        help="Re-judge even if llm_judge.json exists")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only judge N runs (for testing)")
    parser.add_argument("--quiet", action="store_true",
                        help="Less verbose output")
    args = parser.parse_args()

    # Load manifest
    manifest_path = RESULTS_DIR / "run_manifest.json"
    if not manifest_path.exists():
        print(f"ERROR: {manifest_path} not found. Run the benchmark first.")
        sys.exit(1)

    manifest = json.load(open(manifest_path))
    entropy_runs = manifest.get("entropy_runs", [])
    print(f"Loaded manifest: {len(entropy_runs)} entropy-controlled runs")

    # Filter to runs that actually have workspaces
    valid_runs = []
    for run_name in entropy_runs:
        run_dir = RESULTS_DIR / run_name
        if not (run_dir / "summary.json").exists():
            continue
        summary = json.load(open(run_dir / "summary.json"))
        iters = summary.get("iterations", 1)
        ws = run_dir / f"workspace_iter{iters}"
        if not ws.exists():
            ws = run_dir / "workspace_iter1"
        if ws.exists():
            valid_runs.append(run_name)

    print(f"Valid runs with workspaces: {len(valid_runs)}")

    if args.dry_run:
        print(f"\nDRY RUN — would judge {len(valid_runs)} runs:")
        by_judge = defaultdict(list)
        for run_name in valid_runs:
            s = json.load(open(RESULTS_DIR / run_name / "summary.json"))
            model = s.get("model", "unknown")
            judge = select_judge_model(model)
            by_judge[judge].append((run_name, model))

        for judge, items in sorted(by_judge.items()):
            print(f"\n  Judge: {judge} ({len(items)} runs)")
            for run_name, model in items[:5]:
                print(f"    {run_name}  ({model})")
            if len(items) > 5:
                print(f"    ... and {len(items) - 5} more")
        return

    if args.calibrate:
        run_calibration(valid_runs, n=args.calibrate_n)
    else:
        run_full_pipeline(
            valid_runs,
            force=args.force,
            limit=args.limit,
            verbose=not args.quiet,
        )


if __name__ == "__main__":
    main()
