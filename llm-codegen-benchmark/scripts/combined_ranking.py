#!/usr/bin/env python3
"""Combined correctness + quality analysis to answer: what model do we actually pick?"""
import json, os, math
from collections import defaultdict

gate_data = defaultdict(lambda: defaultdict(list))
quality_data = defaultdict(lambda: defaultdict(list))
cost_data = {}

for d in sorted(os.listdir('pilot/results')):
    sp = f'pilot/results/{d}/summary.json'
    qp = f'pilot/results/{d}/quality/llm_judge.json'
    if not os.path.isfile(sp):
        continue
    try:
        s = json.load(open(sp))
        ts = s.get('timestamp', d[:8])
        if ts < '20260207':
            continue
        m = s['model']
        t = s.get('task', '?')
        gates = sum(s.get('gates', {}).values())
        gate_data[m][t].append(gates)
        cost = s.get('cost_usd', 0) or 0
        if m not in cost_data:
            cost_data[m] = []
        cost_data[m].append(cost)

        if os.path.isfile(qp):
            q = json.load(open(qp))
            quality_data[m][t].append(q['composite_scores']['overall_quality'])
    except Exception:
        pass

# Combined view per cell
print('=== TOP 15 MODEL×FRAMEWORK CELLS (60% correctness + 40% quality) ===')
print(f'{"Model":40s} {"Task":18s} {"Gates":>8s} {"Quality":>8s} {"Combined":>9s}')
print('-' * 90)
rows = []
for m in sorted(gate_data):
    for t in sorted(gate_data[m]):
        g = gate_data[m][t]
        q = quality_data[m].get(t, [])
        if not q:
            continue
        gmean = sum(g) / len(g)
        qmean = sum(q) / len(q)
        combined = (gmean / 5) * 0.6 + (qmean / 5) * 0.4
        rows.append((combined, m, t, gmean, qmean, len(g)))

rows.sort(reverse=True)
for combined, m, t, gmean, qmean, n in rows[:15]:
    print(f'{m:40s} {t:18s} {gmean:7.2f}/5 {qmean:7.2f}/5 {combined:8.3f}')

# Overall ranking
print()
print('=== OVERALL RANKING (all 3 frameworks) ===')
model_cells = defaultdict(list)
for combined, m, t, gmean, qmean, n in rows:
    model_cells[m].append((t, gmean, qmean, combined))

print(f'{"Rk":>3s} {"Model":40s} {"Gates":>8s} {"Quality":>8s} {"Combined":>9s} {"σ(gate)":>8s} {"$/run":>8s}')
print('-' * 100)
overall = []
for m, cells in model_cells.items():
    if len(cells) < 3:
        continue
    avg_g = sum(c[1] for c in cells) / len(cells)
    avg_q = sum(c[2] for c in cells) / len(cells)
    avg_c = sum(c[3] for c in cells) / len(cells)
    all_gates = []
    for t in gate_data[m]:
        all_gates.extend(gate_data[m][t])
    gvar = math.sqrt(sum((x - avg_g) ** 2 for x in all_gates) / len(all_gates))
    avg_cost = sum(cost_data.get(m, [0])) / max(len(cost_data.get(m, [1])), 1)
    overall.append((avg_c, m, avg_g, avg_q, gvar, avg_cost))

overall.sort(reverse=True)
for i, (avg_c, m, avg_g, avg_q, gvar, avg_cost) in enumerate(overall, 1):
    cost_str = f'${avg_cost:.3f}' if avg_cost > 0 else '†sub'
    print(f'{i:3d} {m:40s} {avg_g:7.2f}/5 {avg_q:7.2f}/5 {avg_c:8.3f}   {gvar:7.2f} {cost_str:>8s}')

# Per-framework winner
print()
print('=== BEST MODEL PER FRAMEWORK (combined score) ===')
for task in ['fastapi-001', 'aspnetcore-001', 'springboot-001']:
    task_rows = [(c, m, g, q) for c, m, t, g, q, n in rows if t == task]
    task_rows.sort(reverse=True)
    best_c, best_m, best_g, best_q = task_rows[0]
    second_c, second_m, _, _ = task_rows[1]
    print(f'  {task:20s}: {best_m} ({best_g:.2f} gates, {best_q:.2f} quality, combined={best_c:.3f})')
    print(f'  {"":20s}  runner-up: {second_m} (combined={second_c:.3f}, delta={best_c-second_c:.3f})')

# Meta-prompting A/B data
print()
print('=== META-PROMPTING A/B RESULTS ===')
ab_dir = 'pilot/preference_comparisons'
if os.path.isdir(ab_dir):
    for comp in sorted(os.listdir(ab_dir)):
        rp = f'{ab_dir}/{comp}/raw_results.json'
        if not os.path.isfile(rp):
            continue
        try:
            d = json.load(open(rp))
            model = d.get('model', comp)
            task = d.get('task', '?')
            bl = [sum(r.get('gates', {}).values()) for r in d.get('baseline_results', []) if r.get('gates')]
            ad = [sum(r.get('gates', {}).values()) for r in d.get('adapted_results', []) if r.get('gates')]
            if bl and ad:
                bl_mean = sum(bl) / len(bl)
                ad_mean = sum(ad) / len(ad)
                delta = ad_mean - bl_mean
                marker = '↑' if delta > 0 else '↓' if delta < 0 else '='
                print(f'  {model:40s} {task:18s} baseline={bl_mean:.1f} adapted={ad_mean:.1f} Δ={delta:+.1f} {marker}')
        except Exception:
            pass
