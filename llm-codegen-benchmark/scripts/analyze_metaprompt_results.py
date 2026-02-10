#!/usr/bin/env python3
"""
Analyze Meta-Prompting A/B Test Results

Reads raw_results.json from each comparison directory and produces:
1. Per-model gate pass rates (baseline vs adapted)
2. Mann-Whitney U tests per model
3. Overall sign test across models
4. Summary suitable for paper §4.4 / §5.4 update
"""
import json
import math
import os
import statistics
import sys
from pathlib import Path

PILOT_DIR = Path(__file__).parent
COMPARISONS_DIR = PILOT_DIR / "preference_comparisons"


def mann_whitney_u(x, y):
    """Exact Mann-Whitney U for small samples with normal approximation p-value."""
    nx, ny = len(x), len(y)
    u = 0
    for xi in x:
        for yi in y:
            if xi < yi:
                u += 1
            elif xi == yi:
                u += 0.5
    u2 = nx * ny - u
    U = min(u, u2)
    mu = nx * ny / 2
    sigma = ((nx * ny * (nx + ny + 1)) / 12) ** 0.5
    if sigma == 0:
        return U, 0.0, 1.0
    z = (U - mu) / sigma
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return U, z, p


def load_results(date_prefix="20260209"):
    """Load all A/B comparison data from a given date."""
    results = []
    for d in sorted(os.listdir(COMPARISONS_DIR)):
        if not d.startswith(date_prefix):
            continue
        raw = COMPARISONS_DIR / d / "raw_results.json"
        if not raw.is_file():
            continue
        data = json.load(open(raw))
        model = data.get("model", d)
        bl = data.get("baseline_results", [])
        ad = data.get("adapted_results", [])
        bl_gates = [sum(r.get("gates", {}).values()) for r in bl if r.get("gates")]
        ad_gates = [sum(r.get("gates", {}).values()) for r in ad if r.get("gates")]
        if not bl_gates or not ad_gates:
            print(f"  ⚠ {model}: skipped (baseline={len(bl_gates)}, adapted={len(ad_gates)} valid runs)")
            continue
        results.append((model, bl_gates, ad_gates))
    return results


def analyze(results):
    """Full statistical analysis."""
    print("=" * 90)
    print("META-PROMPTING A/B TEST RESULTS — FastAPI-001 (Task: Add Orders CRUD)")
    print("=" * 90)
    print()

    # Per-model summary
    header = f"{'Model':35s} {'Baseline':>12s} {'Adapted':>12s} {'Δ':>6s} {'Dir':>8s}"
    print(header)
    print("-" * 80)

    improved = degraded = neutral = 0
    total_bl = total_ad = 0.0

    for model, bl, ad in results:
        bl_avg = sum(bl) / len(bl)
        ad_avg = sum(ad) / len(ad)
        diff = ad_avg - bl_avg
        total_bl += bl_avg
        total_ad += ad_avg

        if diff > 0.1:
            direction = "▲ Better"
            improved += 1
        elif diff < -0.1:
            direction = "▼ Worse"
            degraded += 1
        else:
            direction = "= Same"
            neutral += 1

        bl_str = f"{bl_avg:.2f}/5 (n={len(bl)})"
        ad_str = f"{ad_avg:.2f}/5 (n={len(ad)})"
        print(f"{model:35s} {bl_str:>12s} {ad_str:>12s} {diff:>+6.2f} {direction:>8s}")

    n = len(results)
    avg_bl = total_bl / n
    avg_ad = total_ad / n
    avg_diff = avg_ad - avg_bl
    print("-" * 80)
    print(f"{'MEAN':35s} {avg_bl:>8.2f}/5    {avg_ad:>8.2f}/5    {avg_diff:>+6.2f}")
    print()
    print(f"Models improved:  {improved}/{n}")
    print(f"Models degraded:  {degraded}/{n}")
    print(f"Models unchanged: {neutral}/{n}")
    print()

    # Mann-Whitney U per model
    print("=" * 90)
    print("STATISTICAL TESTS (Mann-Whitney U, two-sided, n=5 per condition)")
    print("=" * 90)
    print()
    print(f"{'Model':35s} {'U':>5s} {'z':>7s} {'p':>7s}  {'Sig?':>13s}  {'d':>8s}")
    print("-" * 85)

    sig_count = 0
    for model, bl, ad in results:
        U, z, p = mann_whitney_u(bl, ad)
        bl_avg = sum(bl) / len(bl)
        ad_avg = sum(ad) / len(ad)
        diff = ad_avg - bl_avg
        bl_std = statistics.stdev(bl) if len(bl) > 1 else 0
        ad_std = statistics.stdev(ad) if len(ad) > 1 else 0
        pooled = ((bl_std ** 2 + ad_std ** 2) / 2) ** 0.5
        d = diff / pooled if pooled > 0 else 0
        sig = "YES (p<0.05)" if p < 0.05 else "no"
        if p < 0.05:
            sig_count += 1
        print(f"{model:35s} {U:>5.1f} {z:>7.2f} {p:>7.3f}  {sig:>13s}  d={d:>+5.2f}")

    print("-" * 85)
    print(f"Significant at α=0.05: {sig_count}/{n} models")
    print()

    # Overall sign test
    print("=" * 90)
    print("OVERALL EFFECT: Sign test across models")
    print("=" * 90)
    print(f"  Improved: {improved}, Degraded: {degraded}, Tied: {neutral}")
    nn = improved + degraded
    if nn > 0:
        k = min(improved, degraded)
        p_binom = 0
        for i in range(0, k + 1):
            p_binom += math.comb(nn, i) * (0.5 ** nn)
        p_binom *= 2
        p_binom = min(p_binom, 1.0)
        print(f"  Sign test (excl. ties): {improved}/{nn} improved, p={p_binom:.3f}")
    else:
        print("  All ties — no test possible")
    print()
    pct = (avg_diff / avg_bl * 100) if avg_bl else 0
    print(f"Mean gate improvement: {avg_diff:+.2f} gates ({pct:+.1f}%)")
    print()

    # Individual run details
    print("=" * 90)
    print("PER-RUN DETAIL")
    print("=" * 90)
    for model, bl, ad in results:
        bl_str = ",".join(str(g) for g in bl)
        ad_str = ",".join(str(g) for g in ad)
        print(f"  {model:35s}  B=[{bl_str}]  A=[{ad_str}]")
    print()

    # Paper-ready summary
    print("=" * 90)
    print("PAPER-READY SUMMARY (for §4.4 / §5.4)")
    print("=" * 90)
    print()
    print(f"Expanded A/B test: {n} models × n=5 per condition on fastapi-001.")
    print(f"Mean gates passed: baseline {avg_bl:.2f}/5, adapted {avg_ad:.2f}/5 ({avg_diff:+.2f}, {pct:+.1f}%).")
    print(f"Direction: {improved} improved, {degraded} degraded, {neutral} unchanged.")
    print(f"Individually significant (MWU, α=0.05): {sig_count}/{n} models.")
    if nn > 0:
        print(f"Sign test across models: p={p_binom:.3f} ({'significant' if p_binom < 0.05 else 'not significant'} at α=0.05).")
    print()
    if improved > degraded:
        print("Conclusion: Meta-prompting shows a POSITIVE trend overall, but the effect")
        print("is model-dependent. Strong beneficiaries and clear losers exist.")
    elif improved == degraded:
        print("Conclusion: Meta-prompting shows MIXED results. Approximately equal numbers")
        print("of models benefit and are harmed. The intervention is not universally helpful.")
    else:
        print("Conclusion: Meta-prompting shows a NEGATIVE trend overall. More models are")
        print("harmed than helped by preference-adapted prompting.")


def main():
    date_prefix = sys.argv[1] if len(sys.argv) > 1 else "20260209"
    results = load_results(date_prefix)
    if not results:
        print(f"No valid comparison data found for date prefix: {date_prefix}")
        sys.exit(1)
    analyze(results)


if __name__ == "__main__":
    main()
