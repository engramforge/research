#!/usr/bin/env python3
"""
Analyze entropy-controlled benchmark runs and generate statistics report.

This aggregates multiple runs per model/task combination and calculates
mean, standard deviation, and confidence intervals.
"""

import json
import statistics
from pathlib import Path
from collections import defaultdict
from datetime import datetime

REPO_ROOT = Path(__file__).resolve().parent.parent
RESULTS_DIR = REPO_ROOT / "results"

def load_recent_runs(since_timestamp="20260207-083000"):
    """Load all runs since the given timestamp."""
    runs = []
    
    for result_dir in RESULTS_DIR.glob("*"):
        if not result_dir.is_dir():
            continue
        
        # Check if this is after our cutoff
        if result_dir.name < since_timestamp:
            continue
        
        summary_file = result_dir / "summary.json"
        if not summary_file.exists():
            continue
        
        try:
            with open(summary_file) as f:
                data = json.load(f)
                runs.append({
                    'dir': result_dir.name,
                    'model': data['model'],
                    'task': data['task'],
                    'timestamp': data['timestamp'],
                    'gates': data['gates'],
                    'metrics': data['metrics'],
                })
        except Exception as e:
            print(f"Warning: Could not load {summary_file}: {e}")
            continue
    
    return runs

def group_runs(runs):
    """Group runs by model and task."""
    grouped = defaultdict(list)
    
    for run in runs:
        key = (run['model'], run['task'])
        grouped[key].append(run)
    
    return grouped

def calculate_stats(runs):
    """Calculate statistics for a group of runs."""
    if not runs:
        return None
    
    # Gate scores
    gate_scores = [sum(1 for v in r['gates'].values() if v) for r in runs]
    
    # Per-gate statistics
    gate_stats = {}
    for gate_name in ['diff_extracted', 'diff_applied', 'tests_passed', 'mypy_passed', 'ruff_passed']:
        values = [1 if r['gates'].get(gate_name, False) else 0 for r in runs]
        gate_stats[gate_name] = {
            'pass_rate': sum(values) / len(values),
            'passes': sum(values),
            'total': len(values),
        }
    
    # Calculate mean and std
    mean_gates = statistics.mean(gate_scores)
    std_gates = statistics.stdev(gate_scores) if len(gate_scores) > 1 else 0.0
    
    # Coefficient of variation (for confidence estimate)
    cv = std_gates / mean_gates if mean_gates > 0 else 1.0
    confidence = max(0.0, 1.0 - cv)
    
    # Confidence interval (95%)
    if len(gate_scores) > 1:
        margin = 1.96 * (std_gates / (len(gate_scores) ** 0.5))
        ci_low = max(0, mean_gates - margin)
        ci_high = min(5, mean_gates + margin)
    else:
        ci_low = ci_high = mean_gates
    
    # Cost statistics
    costs = [r['metrics'].get('estimated_cost_usd', 0) for r in runs]
    mean_cost = statistics.mean(costs)
    
    return {
        'runs': len(runs),
        'gate_scores': gate_scores,
        'mean_gates': mean_gates,
        'std_gates': std_gates,
        'confidence': confidence,
        'confidence_interval': (ci_low, ci_high),
        'gate_stats': gate_stats,
        'mean_cost': mean_cost,
        'total_cost': sum(costs),
    }

def format_stats_table(grouped_stats):
    """Format statistics as a markdown table."""
    lines = []
    lines.append("# Entropy-Controlled Benchmark Results")
    lines.append("")
    lines.append(f"**Generated:** {datetime.now().astimezone().strftime('%Y-%m-%dT%H:%M:%S%z')}")
    lines.append("")
    lines.append("## Summary Statistics")
    lines.append("")
    lines.append("| Model | Task | Runs | Gates Passed | Confidence | Pass Rate | Cost |")
    lines.append("|-------|------|------|--------------|------------|-----------|------|")
    
    # Sort by model then task
    for (model, task), stats in sorted(grouped_stats.items()):
        if stats is None:
            continue
        
        gates_str = f"{stats['mean_gates']:.2f} ± {stats['std_gates']:.2f}"
        conf_str = f"{stats['confidence']:.1%}"
        ci_str = f"[{stats['confidence_interval'][0]:.2f}, {stats['confidence_interval'][1]:.2f}]"
        
        # Overall pass rate (how many runs got 5/5)
        perfect_runs = sum(1 for score in stats['gate_scores'] if score == 5)
        pass_rate = perfect_runs / stats['runs']
        
        lines.append(f"| {model} | {task} | {stats['runs']} | {gates_str} | {conf_str} | {pass_rate:.0%} | ${stats['mean_cost']:.4f} |")
    
    lines.append("")
    lines.append("## Detailed Gate Statistics")
    lines.append("")
    
    for (model, task), stats in sorted(grouped_stats.items()):
        if stats is None:
            continue
        
        lines.append(f"### {model} - {task}")
        lines.append("")
        lines.append(f"- **Runs:** {stats['runs']}")
        lines.append(f"- **Mean Gates:** {stats['mean_gates']:.2f} ± {stats['std_gates']:.2f} / 5")
        lines.append(f"- **Confidence:** {stats['confidence']:.1%}")
        lines.append(f"- **95% CI:** [{stats['confidence_interval'][0]:.2f}, {stats['confidence_interval'][1]:.2f}]")
        lines.append(f"- **Cost:** ${stats['mean_cost']:.4f} per run, ${stats['total_cost']:.4f} total")
        lines.append("")
        lines.append("Gate-by-gate breakdown:")
        lines.append("")
        
        for gate_name, gate_stat in stats['gate_stats'].items():
            lines.append(f"- **{gate_name}:** {gate_stat['passes']}/{gate_stat['total']} ({gate_stat['pass_rate']:.0%})")
        
        lines.append("")
        lines.append(f"Individual run scores: {stats['gate_scores']}")
        lines.append("")
    
    return "\n".join(lines)

def main():
    print("Loading entropy-controlled benchmark runs...")
    runs = load_recent_runs()
    print(f"Found {len(runs)} runs")
    
    print("\nGrouping by model and task...")
    grouped = group_runs(runs)
    print(f"Found {len(grouped)} model/task combinations")
    
    print("\nCalculating statistics...")
    grouped_stats = {}
    for key, run_list in grouped.items():
        grouped_stats[key] = calculate_stats(run_list)
    
    print("\nGenerating report...")
    report = format_stats_table(grouped_stats)
    
    output_file = REPO_ROOT / "ENTROPY_RESULTS.md"
    output_file.write_text(report)
    
    print(f"\n✓ Report saved to: {output_file}")
    print("\nPreview:")
    print("=" * 70)
    print(report[:1500])
    print("...")

if __name__ == "__main__":
    main()
