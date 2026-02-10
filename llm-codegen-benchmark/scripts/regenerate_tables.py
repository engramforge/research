#!/usr/bin/env python3
"""
Regenerate paper tables from the clean n=5 dataset in pilot/results/.
Reads only top-level run dirs (skips _smoke_tests, _excess_entropy, _incomplete, etc.).
Outputs markdown tables ready to paste into the paper.
"""
import json, os, math
from collections import defaultdict

RESULTS = 'pilot/results'
SKIP_PREFIXES = ('_', '.')

# Model display name mapping
DISPLAY_NAMES = {
    'claude-sonnet-4.5': 'Claude Sonnet 4.5',
    'claude-opus-4.6': 'Claude Opus 4.6',
    'gemini:gemini-3-flash-preview': 'Gemini 3 Flash Preview',
    'gemini:gemini-3-pro-preview': 'Gemini 3 Pro Preview',
    'gpt-4o': 'GPT-4o',
    'gpt-4o-mini': 'GPT-4o-mini',
    'gpt-5.2': 'GPT-5.2',
    'gemini:gemini-2.5-pro': 'Gemini 2.5 Pro',
    'gemini:gemini-2.5-flash': 'Gemini 2.5 Flash',
    'cloud:deepseek-v3.2': 'DeepSeek V3.2',
    'cloud:qwen3-coder-next': 'Qwen3-Coder-Next',
}

TASK_DISPLAY = {
    'fastapi-001': 'fastapi-001',
    'aspnetcore-001': 'aspnetcore-001',
    'springboot-001': 'springboot-001',
}

# Gate names in order (JSON key → display name)
GATES = [
    ('diff_extracted', 'Diff Extract'),
    ('diff_applied', 'Diff Apply'),
    ('tests_passed', 'Tests'),
    ('mypy_passed', 'Types'),
    ('ruff_passed', 'Lint'),
]


def mean_std(values):
    n = len(values)
    if n == 0:
        return 0, 0
    mu = sum(values) / n
    if n == 1:
        return mu, 0
    var = sum((x - mu) ** 2 for x in values) / (n - 1)
    return mu, math.sqrt(var)


def ci95(values):
    n = len(values)
    mu, sd = mean_std(values)
    if n <= 1:
        return mu, mu
    t_val = 2.776  # t critical for df=4 (n=5), two-tailed 95%
    margin = t_val * sd / math.sqrt(n)
    return max(0, mu - margin), min(5, mu + margin)


# Load all runs from clean dataset
runs = []
for d in sorted(os.listdir(RESULTS)):
    if any(d.startswith(p) for p in SKIP_PREFIXES):
        continue
    path = os.path.join(RESULTS, d)
    if not os.path.isdir(path):
        continue
    sp = os.path.join(path, 'summary.json')
    if not os.path.isfile(sp):
        continue
    try:
        s = json.load(open(sp))
        runs.append(s)
    except:
        pass

print(f"Loaded {len(runs)} runs from clean dataset")

# Group by model|task
grid = defaultdict(list)
for r in runs:
    model = r.get('model', '?')
    task = r.get('task', '?')
    grid[f"{model}|{task}"].append(r)

# Compute per-cell stats
cells = {}
for key in sorted(grid):
    model_id, task = key.split('|')
    cell_runs = grid[key]
    gates_list = [sum(1 for v in r.get('gates', {}).values() if v) for r in cell_runs]
    n = len(cell_runs)
    mu, sd = mean_std(gates_list)
    lo, hi = ci95(gates_list)
    perfect = sum(1 for g in gates_list if g == 5) / n * 100

    # Per-gate pass rates
    gate_pass = {}
    for gate_key, gate_label in GATES:
        passed = sum(1 for r in cell_runs if r.get('gates', {}).get(gate_key, False))
        gate_pass[gate_key] = passed / n * 100

    cost = [r.get('metrics', {}).get('total_cost_usd') or r.get('metrics', {}).get('estimated_cost_usd', 0) for r in cell_runs]
    cost = [c for c in cost if c and c > 0]
    avg_cost = sum(cost) / len(cost) if cost else 0

    cells[key] = {
        'model_id': model_id,
        'model': DISPLAY_NAMES.get(model_id, model_id),
        'task': task,
        'n': n,
        'mean': mu,
        'std': sd,
        'ci_lo': lo,
        'ci_hi': hi,
        'perfect_rate': perfect,
        'gate_pass': gate_pass,
        'avg_cost': avg_cost,
        'gates_list': gates_list,
    }

# ============================================================
# TABLE 1: Summary Table
# ============================================================
print("\n\n#### Summary Table\n")
print("| Model | Task | n | Gates Passed | 95% CI | Perfect Rate | Cost/Run |")
print("|-------|------|---|--------------|--------|--------------|----------|")

# Sort by model aggregate (descending)
model_agg = defaultdict(list)
for c in cells.values():
    model_agg[c['model']].append(c['mean'])
model_order = sorted(model_agg, key=lambda m: sum(model_agg[m]) / len(model_agg[m]), reverse=True)

task_order = ['fastapi-001', 'aspnetcore-001', 'springboot-001']
for model_name in model_order:
    for task in task_order:
        # Find matching cell
        for c in cells.values():
            if c['model'] == model_name and c['task'] == task:
                cost_str = f"${c['avg_cost']:.3f}" if c['avg_cost'] > 0 else "†sub"
                print(f"| {c['model']} | {c['task']} | {c['n']} | "
                      f"{c['mean']:.2f} ± {c['std']:.2f} | "
                      f"[{c['ci_lo']:.2f}, {c['ci_hi']:.2f}] | "
                      f"{c['perfect_rate']:.0f}% | {cost_str} |")
                break

# ============================================================
# TABLE 2: Per-Gate Pass Rates
# ============================================================
print("\n\n#### Per-Gate Pass Rates (All Tasks Combined)\n")
print("| Model | n | Diff Extract | Diff Apply | Tests | Types | Lint |")
print("|-------|---|-------------|------------|-------|-------|------|")

for model_name in model_order:
    model_cells = [c for c in cells.values() if c['model'] == model_name]
    total_n = sum(c['n'] for c in model_cells)
    # Average gate pass rates across tasks
    gate_totals = {g[0]: 0 for g in GATES}
    gate_counts = {g[0]: 0 for g in GATES}
    for c in model_cells:
        for gate_key, gate_label in GATES:
            # Count actual passes, not percentages
            gate_totals[gate_key] += c['gate_pass'][gate_key] * c['n'] / 100
            gate_counts[gate_key] += c['n']

    gate_pcts = {}
    for gate_key, gate_label in GATES:
        gate_pcts[gate_key] = gate_totals[gate_key] / gate_counts[gate_key] * 100 if gate_counts[gate_key] > 0 else 0

    print(f"| {model_name} | {total_n} | "
          f"{gate_pcts['diff_extracted']:.0f}% | {gate_pcts['diff_applied']:.0f}% | "
          f"{gate_pcts['tests_passed']:.0f}% | {gate_pcts['mypy_passed']:.0f}% | "
          f"{gate_pcts['ruff_passed']:.0f}% |")

# ============================================================
# TABLE 3: Variance by framework
# ============================================================
print("\n\n#### Variance by Framework (σ)\n")
print("| Model | FastAPI σ | ASP.NET σ | Spring Boot σ |")
print("|-------|----------|-----------|---------------|")
for model_name in model_order:
    row = f"| {model_name}"
    for task in task_order:
        for c in cells.values():
            if c['model'] == model_name and c['task'] == task:
                row += f" | {c['std']:.2f}"
                break
    row += " |"
    print(row)

# ============================================================
# AGGREGATE RANKING
# ============================================================
print("\n\n### Model Rankings (Entropy-Controlled, n=5 per cell, temperature=0.2)\n")
print("| Rank | Model | Mean Gates | σ | Avg Cost | Notes |")
print("|------|-------|-----------|---|----------|-------|")
rank = 0
for model_name in model_order:
    rank += 1
    model_cells = [c for c in cells.values() if c['model'] == model_name]
    all_gates = []
    all_costs = []
    for c in model_cells:
        all_gates.extend(c['gates_list'])
        if c['avg_cost'] > 0:
            all_costs.append(c['avg_cost'])
    mu, sd = mean_std(all_gates)
    avg_cost = sum(all_costs) / len(all_costs) if all_costs else 0
    cost_str = f"${avg_cost:.3f}" if avg_cost > 0 else "†sub"
    print(f"| {rank} | {model_name} | {mu:.2f} | {sd:.2f} | {cost_str} | |")

# ============================================================
# GPT-4o-mini FastAPI detail
# ============================================================
print("\n\n#### Individual Run Scores (GPT-4o-mini on FastAPI)\n")
print("Run-by-run detail for the highest-variance model/task combination:\n")
print("```")
for c in cells.values():
    if c['model'] == 'GPT-4o-mini' and c['task'] == 'fastapi-001':
        for i, r in enumerate(grid[f"{c['model_id']}|{c['task']}"]):
            gates_dict = r.get('gates', {})
            gp = sum(1 for v in gates_dict.values() if v)
            checks = []
            for gate_key, gate_label in GATES:
                passed = gates_dict.get(gate_key, False)
                checks.append(f"{'✓' if passed else '✗'} {gate_label.lower()}")
            print(f"Run {i+1}:  {gp}/5 gates  [{', '.join(checks)}]")
        mu, sd = mean_std(c['gates_list'])
        lo, hi = ci95(c['gates_list'])
        print(f"\nMean: {mu:.2f} ± {sd:.2f} / 5 gates")
        print(f"95% CI: [{lo:.2f}, {hi:.2f}]")
        break
print("```")

print(f"\n\nTotal: {len(runs)} runs, {len(grid)} cells, all n=5")
