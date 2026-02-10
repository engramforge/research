#!/usr/bin/env python3
"""
A/B Testing for Model Preferences - Phase 3 of Meta-Prompting Experiment

This script runs benchmarks with and without adaptive prompting to measure
the impact of using model-stated preferences on code generation quality.

Usage:
    python compare_preference_impact.py --model gpt-4o-mini --task fastapi-001 --runs 3
    python compare_preference_impact.py --model claude-sonnet-4.5 --runs 5 --all-tasks
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent))

from run_benchmark import run_benchmark
from weighted_scoring import QualityScorer


PILOT_DIR = Path(__file__).parent
RESULTS_DIR = PILOT_DIR / "results"
COMPARISON_RESULTS_DIR = PILOT_DIR / "preference_comparisons"


def run_ab_test(
    model: str, 
    task: str, 
    runs: int = 3,
    verbose: bool = True
) -> Tuple[List[Dict], List[Dict]]:
    """
    Run A/B test comparing baseline vs preference-adapted prompts.
    
    Args:
        model: Model to test
        task: Task ID
        runs: Number of runs per condition
        verbose: Print progress
    
    Returns:
        Tuple of (baseline_results, adapted_results)
    """
    COMPARISON_RESULTS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    comparison_dir = COMPARISON_RESULTS_DIR / f"{timestamp}-{model.replace(':', '-')}-{task}"
    comparison_dir.mkdir(parents=True, exist_ok=True)
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"A/B TEST: {model} on {task}")
        print(f"{'='*70}")
        print(f"Runs per condition: {runs}")
        print(f"Output directory: {comparison_dir}")
        print(f"{'='*70}\n")
    
    baseline_results = []
    adapted_results = []
    
    # Run baseline condition (no preferences)
    if verbose:
        print(f"\n{'#'*70}")
        print(f"CONDITION A: BASELINE (No adaptive prompting)")
        print(f"{'#'*70}\n")
    
    for i in range(1, runs + 1):
        if verbose:
            print(f"\n--- Baseline Run {i}/{runs} ---")
        
        try:
            result = run_benchmark(
                model=model,
                task=task,
                dry_run=False,
                iterations=1,
                use_model_preferences=False
            )
            baseline_results.append(result)
            
            if verbose:
                print(f"✓ Baseline run {i} complete")
                print(f"  Gates: {sum(result['gates'].values())}/{len(result['gates'])} passed")
            
            # Small delay between runs
            time.sleep(2)
            
        except Exception as e:
            print(f"✗ Error in baseline run {i}: {e}")
            continue
    
    # Run adapted condition (with preferences)
    if verbose:
        print(f"\n{'#'*70}")
        print(f"CONDITION B: ADAPTED (With model preferences)")
        print(f"{'#'*70}\n")
    
    for i in range(1, runs + 1):
        if verbose:
            print(f"\n--- Adapted Run {i}/{runs} ---")
        
        try:
            result = run_benchmark(
                model=model,
                task=task,
                dry_run=False,
                iterations=1,
                use_model_preferences=True
            )
            adapted_results.append(result)
            
            if verbose:
                print(f"✓ Adapted run {i} complete")
                print(f"  Gates: {sum(result['gates'].values())}/{len(result['gates'])} passed")
            
            # Small delay between runs
            time.sleep(2)
            
        except Exception as e:
            print(f"✗ Error in adapted run {i}: {e}")
            continue
    
    # Save raw results
    comparison_data = {
        "model": model,
        "task": task,
        "timestamp": timestamp,
        "runs_per_condition": runs,
        "baseline_results": baseline_results,
        "adapted_results": adapted_results,
    }
    
    results_file = comparison_dir / "raw_results.json"
    results_file.write_text(json.dumps(comparison_data, indent=2))
    
    if verbose:
        print(f"\n✓ Raw results saved: {results_file}")
    
    return baseline_results, adapted_results


def calculate_weighted_scores(results: List[Dict], task: str) -> List[Dict]:
    """
    Calculate weighted quality scores for a list of benchmark results.
    """
    scored_results = []
    
    for result in results:
        # Find the workspace directory
        result_dirs = list(RESULTS_DIR.glob(f"*{result['model'].replace(':', '-')}*"))
        if not result_dirs:
            print(f"Warning: Could not find result directory for {result['model']}")
            continue
        
        # Use most recent matching directory
        result_dir = sorted(result_dirs, key=lambda p: p.name)[-1]
        workspace = result_dir / f"workspace_iter{result.get('iterations', 1)}"
        
        if not workspace.exists():
            print(f"Warning: Workspace not found: {workspace}")
            continue
        
        try:
            scorer = QualityScorer(workspace, task)
            scores = scorer.calculate_weighted_score(result)
            
            scored_results.append({
                "result": result,
                "weighted_score": scores["weighted_score"],
                "attribute_scores": scores["scores"],
                "workspace": str(workspace),
            })
        except Exception as e:
            print(f"Warning: Could not score result: {e}")
            continue
    
    return scored_results


def analyze_comparison(
    baseline_scores: List[Dict],
    adapted_scores: List[Dict],
    model: str,
    task: str
) -> Dict:
    """
    Analyze the comparison between baseline and adapted conditions.
    """
    if not baseline_scores or not adapted_scores:
        return {
            "model": model,
            "task": task,
            "error": "Insufficient scored data for comparison (weighted scoring failed)",
            "baseline_count": len(baseline_scores),
            "adapted_count": len(adapted_scores),
        }
    
    # Extract weighted scores
    baseline_values = [s["weighted_score"] for s in baseline_scores]
    adapted_values = [s["weighted_score"] for s in adapted_scores]
    
    # Calculate statistics
    baseline_mean = sum(baseline_values) / len(baseline_values)
    adapted_mean = sum(adapted_values) / len(adapted_values)
    
    baseline_variance = sum((x - baseline_mean) ** 2 for x in baseline_values) / len(baseline_values)
    adapted_variance = sum((x - adapted_mean) ** 2 for x in adapted_values) / len(adapted_values)
    
    baseline_std = baseline_variance ** 0.5
    adapted_std = adapted_variance ** 0.5
    
    # Calculate improvement
    absolute_improvement = adapted_mean - baseline_mean
    relative_improvement = (absolute_improvement / baseline_mean * 100) if baseline_mean > 0 else 0
    
    # Determine statistical significance (simple t-test approximation)
    # For proper stats, would use scipy.stats.ttest_ind
    pooled_std = ((baseline_variance + adapted_variance) / 2) ** 0.5
    effect_size = absolute_improvement / pooled_std if pooled_std > 0 else 0
    
    # Cohen's d interpretation: 0.2 small, 0.5 medium, 0.8 large
    if abs(effect_size) < 0.2:
        significance = "negligible"
    elif abs(effect_size) < 0.5:
        significance = "small"
    elif abs(effect_size) < 0.8:
        significance = "medium"
    else:
        significance = "large"
    
    # Gate pass rates
    baseline_gates = [sum(s["result"]["gates"].values()) for s in baseline_scores]
    adapted_gates = [sum(s["result"]["gates"].values()) for s in adapted_scores]
    
    baseline_gate_rate = sum(baseline_gates) / (len(baseline_gates) * len(baseline_scores[0]["result"]["gates"]))
    adapted_gate_rate = sum(adapted_gates) / (len(adapted_gates) * len(adapted_scores[0]["result"]["gates"]))
    
    return {
        "model": model,
        "task": task,
        "baseline": {
            "mean": baseline_mean,
            "std": baseline_std,
            "values": baseline_values,
            "gate_pass_rate": baseline_gate_rate,
            "runs": len(baseline_scores),
        },
        "adapted": {
            "mean": adapted_mean,
            "std": adapted_std,
            "values": adapted_values,
            "gate_pass_rate": adapted_gate_rate,
            "runs": len(adapted_scores),
        },
        "comparison": {
            "absolute_improvement": absolute_improvement,
            "relative_improvement_pct": relative_improvement,
            "effect_size": effect_size,
            "significance": significance,
            "gate_improvement_pct": (adapted_gate_rate - baseline_gate_rate) * 100,
        }
    }


def print_analysis(analysis: Dict):
    """
    Pretty-print the analysis results.
    """
    print(f"\n{'='*70}")
    print(f"ANALYSIS: {analysis['model']} on {analysis['task']}")
    print(f"{'='*70}\n")
    
    if "error" in analysis:
        print(f"❌ {analysis['error']}")
        return
    
    baseline = analysis["baseline"]
    adapted = analysis["adapted"]
    comp = analysis["comparison"]
    
    print(f"Baseline (No Preferences):")
    print(f"  Mean Quality:     {baseline['mean']:.1%}")
    print(f"  Std Deviation:    {baseline['std']:.1%}")
    print(f"  Gate Pass Rate:   {baseline['gate_pass_rate']:.1%}")
    print(f"  Runs:             {baseline['runs']}")
    
    print(f"\nAdapted (With Preferences):")
    print(f"  Mean Quality:     {adapted['mean']:.1%}")
    print(f"  Std Deviation:    {adapted['std']:.1%}")
    print(f"  Gate Pass Rate:   {adapted['gate_pass_rate']:.1%}")
    print(f"  Runs:             {adapted['runs']}")
    
    print(f"\nComparison:")
    improvement_symbol = "📈" if comp['absolute_improvement'] > 0 else "📉" if comp['absolute_improvement'] < 0 else "➡️"
    print(f"  {improvement_symbol} Quality Change:   {comp['absolute_improvement']:+.1%} ({comp['relative_improvement_pct']:+.1f}%)")
    print(f"  Effect Size:      {comp['effect_size']:.2f} ({comp['significance']})")
    print(f"  Gate Change:      {comp['gate_improvement_pct']:+.1f}%")
    
    print(f"\n{'='*70}")
    
    # Interpretation
    if comp['absolute_improvement'] >= 0.02 and comp['significance'] in ['medium', 'large']:
        print("✅ SUCCESS: Significant quality improvement detected!")
        print("   Recommendation: Enable adaptive prompting for this model")
    elif abs(comp['absolute_improvement']) < 0.01:
        print("➡️  NEUTRAL: No significant quality difference")
        print("   Recommendation: Baseline prompts are sufficient")
    else:
        print("⚠️  INCONCLUSIVE: Small or negative effect")
        print("   Recommendation: More testing needed or avoid adaptive prompting")
    
    print(f"{'='*70}\n")


def main():
    parser = argparse.ArgumentParser(description="A/B test model preferences impact")
    parser.add_argument("--model", required=True, help="Model to test (e.g., gpt-4o-mini)")
    parser.add_argument("--task", default="fastapi-001", help="Task ID (default: fastapi-001)")
    parser.add_argument("--runs", type=int, default=3, help="Runs per condition (default: 3)")
    parser.add_argument("--all-tasks", action="store_true", help="Test on all tasks")
    parser.add_argument("--quiet", action="store_true", help="Minimal output")
    
    args = parser.parse_args()
    
    tasks = [args.task]
    if args.all_tasks:
        tasks = ["fastapi-001", "aspnetcore-001", "springboot-001"]
    
    all_analyses = []
    
    for task in tasks:
        # Run A/B test
        baseline_results, adapted_results = run_ab_test(
            model=args.model,
            task=task,
            runs=args.runs,
            verbose=not args.quiet
        )
        
        if not baseline_results or not adapted_results:
            print(f"⚠️  Skipping analysis for {task} - insufficient data")
            continue
        
        # Calculate weighted scores
        print(f"\nCalculating weighted quality scores...")
        baseline_scores = calculate_weighted_scores(baseline_results, task)
        adapted_scores = calculate_weighted_scores(adapted_results, task)
        
        # Analyze — fall back to gate-based analysis if weighted scoring failed
        if not baseline_scores and baseline_results:
            print("  ⚠️  Weighted scoring failed, using gate-based analysis")
            baseline_scores = [{
                "result": r,
                "weighted_score": sum(r.get("gates", {}).values()) / max(len(r.get("gates", {})), 1),
                "attribute_scores": {},
                "workspace": "N/A",
            } for r in baseline_results]
        if not adapted_scores and adapted_results:
            adapted_scores = [{
                "result": r,
                "weighted_score": sum(r.get("gates", {}).values()) / max(len(r.get("gates", {})), 1),
                "attribute_scores": {},
                "workspace": "N/A",
            } for r in adapted_results]
        
        analysis = analyze_comparison(baseline_scores, adapted_scores, args.model, task)
        all_analyses.append(analysis)
        
        # Print results
        print_analysis(analysis)
        
        # Save analysis — reuse the comparison dir that run_ab_test created
        # Find the most recent comparison dir for this model/task
        matching_dirs = sorted(COMPARISON_RESULTS_DIR.glob(f"*-{args.model.replace(':', '-')}-{task}"))
        if matching_dirs:
            comparison_dir = matching_dirs[-1]
        else:
            timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
            comparison_dir = COMPARISON_RESULTS_DIR / f"{timestamp}-{args.model.replace(':', '-')}-{task}"
            comparison_dir.mkdir(parents=True, exist_ok=True)
        analysis_file = comparison_dir / "analysis.json"
        analysis_file.write_text(json.dumps(analysis, indent=2))
        print(f"✓ Analysis saved: {analysis_file}")
    
    # Summary across all tasks
    if len(all_analyses) > 1:
        print(f"\n{'='*70}")
        print(f"SUMMARY ACROSS ALL TASKS")
        print(f"{'='*70}\n")
        
        for analysis in all_analyses:
            comp = analysis["comparison"]
            symbol = "✅" if comp['absolute_improvement'] >= 0.02 else "➡️" if abs(comp['absolute_improvement']) < 0.01 else "⚠️"
            print(f"{symbol} {analysis['task']}: {comp['absolute_improvement']:+.1%} ({comp['significance']} effect)")


if __name__ == "__main__":
    main()
