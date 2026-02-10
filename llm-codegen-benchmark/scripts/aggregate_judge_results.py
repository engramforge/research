#!/usr/bin/env python3
"""Aggregate all 165 LLM judge results into a single summary."""
import json
import os
from collections import defaultdict
from pathlib import Path

RESULTS_DIR = Path("/Users/jgray/projects/ai/llm-codebench/pilot/results")

# Load manifest
manifest = json.load(open(RESULTS_DIR / "run_manifest.json"))
entropy_runs = manifest["entropy_runs"]

all_scores = []
missing = []

for run_name in entropy_runs:
    judge_file = RESULTS_DIR / run_name / "quality" / "llm_judge.json"
    summary_file = RESULTS_DIR / run_name / "summary.json"
    if not judge_file.exists():
        missing.append(run_name)
        continue
    j = json.load(open(judge_file))
    s = json.load(open(summary_file))
    all_scores.append({
        "run": run_name,
        "model": s.get("model", "unknown"),
        "task": s.get("task", "unknown"),
        "judge_model": j.get("judge_model", "unknown"),
        "gates": s.get("gates", {}),
        **j.get("composite_scores", {}),
    })

print(f"Total judge results: {len(all_scores)} / {len(entropy_runs)}")
if missing:
    print(f"Missing: {len(missing)}")
    for m in missing[:5]:
        print(f"  {m}")

# Group by model
by_model = defaultdict(list)
for s in all_scores:
    by_model[s["model"]].append(s)

dims = ["clean_code_index", "pattern_appropriateness", "idiom_score",
        "organization_score", "overall_quality"]

print(f"\n{'Model':40s} {'Overall':>8s} {'CC':>6s} {'Pat':>6s} {'Idiom':>6s} {'Org':>6s} {'n':>4s}")
print("-" * 80)

model_summaries = {}
for model in sorted(by_model, key=lambda m: -sum(s["overall_quality"] for s in by_model[m])/len(by_model[m])):
    scores = by_model[model]
    n = len(scores)
    means = {dim: sum(s[dim] for s in scores) / n for dim in dims}
    model_summaries[model] = {"n": n, **{k: round(v, 3) for k, v in means.items()}}

    print(f"  {model:38s} {means['overall_quality']:6.2f}   {means['clean_code_index']:5.2f} "
          f"{means['pattern_appropriateness']:5.0%} {means['idiom_score']:5.0%} "
          f"{means['organization_score']:5.2f}  {n:3d}")

# Also group by task
print(f"\n\nBy Task:")
by_task = defaultdict(list)
for s in all_scores:
    by_task[s["task"]].append(s)

for task in sorted(by_task):
    scores = by_task[task]
    mean_q = sum(s["overall_quality"] for s in scores) / len(scores)
    print(f"  {task:20s}  mean={mean_q:.2f}  n={len(scores)}")

# Also by model x task
print(f"\n\nModel × Task Grid:")
print(f"{'Model':40s} {'fastapi':>10s} {'aspnetcore':>12s} {'springboot':>12s}")
print("-" * 78)
for model in sorted(by_model, key=lambda m: -model_summaries[m]["overall_quality"]):
    row = {}
    for s in by_model[model]:
        task = s["task"].replace("-001", "")
        row.setdefault(task, []).append(s["overall_quality"])
    cells = []
    for t in ["fastapi", "aspnetcore", "springboot"]:
        if t in row:
            m = sum(row[t]) / len(row[t])
            cells.append(f"{m:.2f} (n={len(row[t])})")
        else:
            cells.append("-")
    print(f"  {model:38s} {cells[0]:>10s} {cells[1]:>12s} {cells[2]:>12s}")

# Save full summary
summary = {
    "total_judged": len(all_scores),
    "total_missing": len(missing),
    "by_model": model_summaries,
    "all_scores": all_scores,
}
out = RESULTS_DIR / "quality_analysis" / "judge_summary_full.json"
json.dump(summary, open(out, "w"), indent=2)
print(f"\nFull summary saved to: {out}")
