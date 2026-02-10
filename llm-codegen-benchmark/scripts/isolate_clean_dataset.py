#!/usr/bin/env python3
"""
Isolate pilot/results into a clean n=5-per-cell dataset.

Actions:
  1. Move pre-Feb-7 smoke-test runs → _smoke_tests/
  2. Move incomplete runs (no summary.json) → _incomplete/
  3. For cells with n>5, move chronologically-latest excess runs → _excess_entropy/
  4. Verify: exactly 33 cells × 5 runs = 165 runs remain

Run with --dry-run first, then without to execute.
"""
import json, os, shutil, sys
from collections import defaultdict

RESULTS = 'pilot/results'
CUTOFF = '20260207'
TARGET_N = 5

DRY_RUN = '--dry-run' in sys.argv
FORCE = '--force' in sys.argv

if DRY_RUN:
    print("=== DRY RUN (no files will be moved) ===\n")


def ensure_dir(path):
    if not DRY_RUN:
        os.makedirs(path, exist_ok=True)


def move(src, dest_dir, reason):
    basename = os.path.basename(src)
    dest = os.path.join(dest_dir, basename)
    print(f"  {'[DRY] ' if DRY_RUN else ''}MOVE {basename} → {os.path.relpath(dest_dir, RESULTS)}/  ({reason})")
    if not DRY_RUN:
        ensure_dir(dest_dir)
        if os.path.exists(dest):
            print(f"    WARNING: destination exists, skipping")
            return False
        shutil.move(src, dest)
    return True


# Categorize all directories
smoke_runs = []
entropy_runs = []  # list of (dir_path, model, task, timestamp)
incomplete = []
special_dirs = {'_smoke_tests', '_archived_uncontrolled_temp', '_excess_entropy', '_incomplete', 'quality_analysis'}

for d in sorted(os.listdir(RESULTS)):
    path = os.path.join(RESULTS, d)
    if not os.path.isdir(path):
        continue
    if d in special_dirs or d.startswith('.'):
        continue

    sp = os.path.join(path, 'summary.json')
    if not os.path.isfile(sp):
        incomplete.append(path)
        continue

    try:
        s = json.load(open(sp))
        ts = s.get('timestamp', d[:8])
        model = s.get('model', '?')
        task = s.get('task', '?')

        if ts < CUTOFF:
            smoke_runs.append(path)
        else:
            entropy_runs.append((path, model, task, ts))
    except Exception:
        incomplete.append(path)

# --- Step 1: Move smoke-test runs ---
smoke_dest = os.path.join(RESULTS, '_smoke_tests')
print(f"STEP 1: Move {len(smoke_runs)} smoke-test runs (pre {CUTOFF})")
for path in smoke_runs:
    move(path, smoke_dest, "smoke-test era")

# --- Step 2: Move incomplete runs ---
incomplete_dest = os.path.join(RESULTS, '_incomplete')
print(f"\nSTEP 2: Move {len(incomplete)} incomplete runs (no summary.json)")
for path in incomplete:
    move(path, incomplete_dest, "no summary.json")

# --- Step 3: Cap entropy runs to n=5 per cell ---
print(f"\nSTEP 3: Cap entropy cells to n={TARGET_N}")
excess_dest = os.path.join(RESULTS, '_excess_entropy')
grid = defaultdict(list)
for path, model, task, ts in entropy_runs:
    grid[f"{model}|{task}"].append((ts, path))

moved_excess = 0
for key in sorted(grid):
    runs = sorted(grid[key], key=lambda x: x[0])  # sort by timestamp
    if len(runs) > TARGET_N:
        # Keep the first TARGET_N, move the rest
        excess = runs[TARGET_N:]
        print(f"  {key}: n={len(runs)}, keeping first {TARGET_N}, moving {len(excess)} excess")
        for ts, path in excess:
            move(path, excess_dest, f"excess (#{TARGET_N+1}+ for {key})")
            moved_excess += 1
    elif len(runs) < TARGET_N:
        print(f"  {key}: n={len(runs)} ← UNDER TARGET (need {TARGET_N - len(runs)} more)")

# --- Step 4: Verify ---
print(f"\n{'=' * 60}")
print("VERIFICATION")
print(f"{'=' * 60}")
remaining = 0
remaining_grid = defaultdict(int)
for d in sorted(os.listdir(RESULTS)):
    path = os.path.join(RESULTS, d)
    if not os.path.isdir(path) or d in special_dirs or d.startswith('.') or d.startswith('_'):
        continue
    sp = os.path.join(path, 'summary.json')
    if not os.path.isfile(sp):
        continue
    try:
        s = json.load(open(sp))
        remaining += 1
        remaining_grid[f"{s['model']}|{s.get('task', '?')}"] += 1
    except:
        pass

if DRY_RUN:
    # Simulate the result
    remaining = len(entropy_runs) - moved_excess
    remaining_grid = {}
    for key in grid:
        remaining_grid[key] = min(len(grid[key]), TARGET_N)

parity_ok = all(v == TARGET_N for v in remaining_grid.values())
print(f"Remaining runs:   {remaining}")
print(f"Cells:            {len(remaining_grid)}")
print(f"All at n={TARGET_N}:      {'✓ YES' if parity_ok else '✗ NO'}")
if not parity_ok:
    for k, v in sorted(remaining_grid.items()):
        if v != TARGET_N:
            print(f"  {k}: n={v}")
print(f"\nSmoke-test moved:  {len(smoke_runs)}")
print(f"Incomplete moved:  {len(incomplete)}")
print(f"Excess moved:      {moved_excess}")
print(f"Total displaced:   {len(smoke_runs) + len(incomplete) + moved_excess}")

if DRY_RUN:
    print("\nRe-run without --dry-run to execute.")
