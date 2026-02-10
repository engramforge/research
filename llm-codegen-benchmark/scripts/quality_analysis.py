#!/usr/bin/env python3
"""Layer 2: Intra-model consistency analysis + Layer 4: Fingerprint extraction.

Reads:  pilot/results/{run_dir}/quality/automated.json (from static_analysis.py)
        pilot/results/{run_dir}/quality/llm_judge.json  (from llm_judge.py)
Writes: pilot/results/quality_analysis/
          intra_model_consistency.json
          model_fingerprints.json
          inter_model_comparison.json
          quality_consistency_frontier.json
          quality_summary.json

Only processes entropy-controlled runs (via run_manifest.json).
"""

import json
import math
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

RESULTS_DIR = Path(__file__).resolve().parent / "results"
OUTPUT_DIR = RESULTS_DIR / "quality_analysis"


def load_quality_data() -> list[dict]:
    """Load automated.json + llm_judge.json for each entropy-controlled run.

    Returns a list of dicts, each containing the automated metrics plus a
    'judge' key with the LLM judge scores (or None if judge data missing).
    """
    manifest = json.load(open(RESULTS_DIR / "run_manifest.json"))
    entropy_dirs = set(manifest["entropy_runs"])

    data = []
    judge_found = 0
    for run_dir_name in entropy_dirs:
        quality_dir = RESULTS_DIR / run_dir_name / "quality"
        automated_file = quality_dir / "automated.json"
        judge_file = quality_dir / "llm_judge.json"

        if not automated_file.exists():
            continue

        d = json.load(open(automated_file))

        # Merge judge data if available
        if judge_file.exists():
            d["judge"] = json.load(open(judge_file))
            judge_found += 1
        else:
            d["judge"] = None

        data.append(d)

    print(f"  Loaded {len(data)} automated + {judge_found} judge results")
    return data


def compute_stats(values: list[float]) -> dict[str, float]:
    """Compute basic statistics for a list of values."""
    if not values:
        return {"n": 0, "mean": 0, "std": 0, "min": 0, "max": 0, "cv": 0}
    n = len(values)
    mean = sum(values) / n
    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
    else:
        std = 0.0
    cv = std / mean if mean > 0 else 0
    return {
        "n": n,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "min": round(min(values), 2),
        "max": round(max(values), 2),
        "cv": round(cv, 3),
    }


def jaccard_similarity(set_a: set, set_b: set) -> float:
    """Compute Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 1.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return round(intersection / union, 3) if union > 0 else 0.0


# ──────────────────────────────────────────────────────────────────────
# Layer 2: Intra-Model Consistency
# ──────────────────────────────────────────────────────────────────────

def compute_intra_model_consistency(data: list[dict]) -> dict[str, Any]:
    """Measure run-to-run variance for each model×language pair."""
    # Group by model × language
    groups = defaultdict(list)
    for d in data:
        key = (d["model"], d["language"])
        groups[key].append(d)

    results = {}
    for (model, language), runs in sorted(groups.items()):
        n = len(runs)
        if n < 2:
            continue  # Need at least 2 runs for variance

        # Structural stability metrics
        locs = [r["aggregate"].get("total_loc", 0) for r in runs]
        func_counts = [
            r["aggregate"].get("total_functions", r["aggregate"].get("total_methods", 0))
            for r in runs
        ]
        complexities = [r["aggregate"].get("total_cyclomatic_complexity", 0) for r in runs]
        nesting = [r["aggregate"].get("max_nesting_depth", 0) for r in runs]

        # Type annotation coverage (Python only)
        type_cov = [r["aggregate"].get("avg_type_annotation_coverage", 0) for r in runs]
        docstring = [r["aggregate"].get("avg_docstring_density", 0) for r in runs]

        # Structure fingerprint similarity (Jaccard over file paths)
        fingerprints = [set(r.get("structure_fingerprint", [])) for r in runs]
        pairwise_jaccard = []
        for i in range(len(fingerprints)):
            for j in range(i + 1, len(fingerprints)):
                pairwise_jaccard.append(jaccard_similarity(fingerprints[i], fingerprints[j]))

        # Naming drift: Jaccard over function/method names
        id_sets = []
        for r in runs:
            ids = r.get("identifiers", {})
            names = set(ids.get("functions", []) + ids.get("methods", []))
            id_sets.append(names)

        naming_jaccard = []
        for i in range(len(id_sets)):
            for j in range(i + 1, len(id_sets)):
                naming_jaccard.append(jaccard_similarity(id_sets[i], id_sets[j]))

        # Gates passed
        gates = [r.get("gates_passed", 0) for r in runs]

        result = {
            "model": model,
            "language": language,
            "n_runs": n,
            "structural_stability": {
                "loc": compute_stats(locs),
                "function_count": compute_stats(func_counts),
                "cyclomatic_complexity": compute_stats(complexities),
                "max_nesting_depth": compute_stats(nesting),
            },
            "quality_stability": {
                "type_annotation_coverage": compute_stats(type_cov),
                "docstring_density": compute_stats(docstring),
            },
            "fingerprint_similarity": {
                "structure_jaccard": compute_stats(pairwise_jaccard),
                "naming_jaccard": compute_stats(naming_jaccard),
            },
            "gate_consistency": {
                "gates_passed": compute_stats([float(g) for g in gates]),
                "perfect_rate": round(sum(1 for g in gates if g == 5) / n, 2),
            },
        }

        results[f"{model}|{language}"] = result

    return results


# ──────────────────────────────────────────────────────────────────────
# Layer 4: Model Generation Fingerprints
# ──────────────────────────────────────────────────────────────────────

def _classify_tendency(values: list[float]) -> str:
    """Classify a tendency as always/sometimes/rarely based on mean."""
    if not values:
        return "unknown"
    mean = sum(values) / len(values)
    if mean >= 0.8:
        return "always"
    elif mean >= 0.3:
        return "sometimes"
    else:
        return "rarely"


def _extract_pattern_signature(judged_runs: list[dict]) -> dict[str, Any]:
    """Aggregate design_patterns across runs into a pattern frequency map.

    For each named pattern, compute:
      - frequency: fraction of runs where it was PRESENT_CORRECT
      - misapplied_rate: fraction where PRESENT_MISAPPLIED
      - absent_expected_rate: fraction where ABSENT_EXPECTED (a gap)
    """
    pattern_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_runs = 0

    for run in judged_runs:
        judge = run.get("judge")
        if not judge:
            continue
        patterns = judge.get("raw_scores", {}).get("design_patterns", [])
        if not patterns:
            continue
        total_runs += 1
        for p in patterns:
            name = p["pattern"]
            status = p["status"]
            pattern_counts[name][status] += 1

    if total_runs == 0:
        return {}

    signature = {}
    for pattern_name, statuses in sorted(pattern_counts.items()):
        total_seen = sum(statuses.values())
        signature[pattern_name] = {
            "present_correct": round(statuses.get("PRESENT_CORRECT", 0) / total_runs, 2),
            "present_misapplied": round(statuses.get("PRESENT_MISAPPLIED", 0) / total_runs, 2),
            "absent_expected": round(statuses.get("ABSENT_EXPECTED", 0) / total_runs, 2),
            "absent_acceptable": round(statuses.get("ABSENT_ACCEPTABLE", 0) / total_runs, 2),
            "n_evaluated": total_seen,
        }

    return {"n_judged_runs": total_runs, "patterns": signature}


def _extract_style_signature(judged_runs: list[dict]) -> dict[str, Any]:
    """Aggregate clean_code subscores into a style profile per model.

    Returns mean + std for each of the 5 clean code dimensions, plus
    composite scores.
    """
    dimensions: dict[str, list[float]] = defaultdict(list)
    composites: dict[str, list[float]] = defaultdict(list)

    for run in judged_runs:
        judge = run.get("judge")
        if not judge:
            continue
        clean_code = judge.get("raw_scores", {}).get("clean_code", {})
        for dim_name, dim_data in clean_code.items():
            if isinstance(dim_data, dict) and "score" in dim_data:
                dimensions[dim_name].append(dim_data["score"])

        comp = judge.get("composite_scores", {})
        for key in ("clean_code_index", "pattern_appropriateness",
                     "idiom_score", "organization_score", "overall_quality"):
            if key in comp:
                composites[key].append(comp[key])

    if not dimensions:
        return {}

    profile = {}
    for dim_name, scores in sorted(dimensions.items()):
        profile[dim_name] = compute_stats(scores)

    composite_stats = {}
    for key, scores in sorted(composites.items()):
        composite_stats[key] = compute_stats(scores)

    return {"dimensions": profile, "composites": composite_stats}


def _extract_idiom_profile(judged_runs: list[dict]) -> dict[str, Any]:
    """Aggregate idiom_adherence statuses into an idiom profile.

    Returns per-idiom classification rates and an overall idiomatic_rate.
    """
    idiom_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    total_runs = 0

    for run in judged_runs:
        judge = run.get("judge")
        if not judge:
            continue
        idioms = judge.get("raw_scores", {}).get("idiom_adherence", [])
        if not idioms:
            continue
        total_runs += 1
        for item in idioms:
            name = item["idiom"]
            status = item["status"]
            idiom_counts[name][status] += 1

    if total_runs == 0:
        return {}

    idiom_profile = {}
    idiomatic_total = 0
    idiom_evaluations = 0

    for idiom_name, statuses in sorted(idiom_counts.items()):
        n = sum(statuses.values())
        idiomatic = statuses.get("IDIOMATIC", 0)
        idiomatic_total += idiomatic
        idiom_evaluations += n
        idiom_profile[idiom_name] = {
            "idiomatic_rate": round(idiomatic / n, 2) if n else 0,
            "functional_rate": round(statuses.get("FUNCTIONAL_NOT_IDIOMATIC", 0) / n, 2) if n else 0,
            "anti_pattern_rate": round(statuses.get("ANTI_PATTERN", 0) / n, 2) if n else 0,
            "n_evaluated": n,
        }

    overall_rate = round(idiomatic_total / idiom_evaluations, 3) if idiom_evaluations else 0

    return {
        "n_judged_runs": total_runs,
        "overall_idiomatic_rate": overall_rate,
        "idioms": idiom_profile,
    }


def _extract_error_handling_philosophy(judged_runs: list[dict], automated_runs: list[dict]) -> dict[str, Any]:
    """Characterize error handling approach from judge + automated data.

    Combines the clean_code.error_handling score with structural indicators.
    """
    error_scores = []
    for run in judged_runs:
        judge = run.get("judge")
        if not judge:
            continue
        eh = judge.get("raw_scores", {}).get("clean_code", {}).get("error_handling", {})
        if isinstance(eh, dict) and "score" in eh:
            error_scores.append(eh["score"])

    if not error_scores:
        return {}

    stats = compute_stats(error_scores)

    # Classify philosophy
    mean = stats["mean"]
    if mean >= 4.5:
        philosophy = "defensive"  # comprehensive error handling
    elif mean >= 3.5:
        philosophy = "pragmatic"  # adequate but not exhaustive
    elif mean >= 2.5:
        philosophy = "minimal"   # basic error paths only
    else:
        philosophy = "optimistic"  # assumes happy path

    return {
        "score_stats": stats,
        "philosophy": philosophy,
    }


def extract_fingerprints(data: list[dict], consistency: dict) -> dict[str, Any]:
    """Extract comprehensive generation signatures per model.

    Combines structural metrics (from automated.json) with qualitative
    assessments (from llm_judge.json) to build a multi-dimensional
    fingerprint for each model.
    """
    # Group by model (across all languages for cross-language fingerprint)
    by_model = defaultdict(list)
    for d in data:
        by_model[d["model"]].append(d)

    fingerprints = {}
    for model, runs in sorted(by_model.items()):
        # Per-language breakdown
        by_lang = defaultdict(list)
        for r in runs:
            by_lang[r["language"]].append(r)

        languages = {}
        for lang, lang_runs in by_lang.items():
            locs = [r["aggregate"].get("total_loc", 0) for r in lang_runs]
            funcs = [
                r["aggregate"].get("total_functions", r["aggregate"].get("total_methods", 0))
                for r in lang_runs
            ]

            # Determine decomposition style
            avg_funcs = sum(funcs) / len(funcs) if funcs else 0
            if avg_funcs <= 5:
                granularity = "coarse"
            elif avg_funcs <= 10:
                granularity = "medium"
            else:
                granularity = "fine"

            avg_loc = sum(locs) / len(locs) if locs else 0

            # Automated framework-specific patterns
            auto_patterns = {}
            if lang == "python":
                async_ratios = [r["aggregate"].get("async_ratio", 0) for r in lang_runs]
                type_covs = [r["aggregate"].get("avg_type_annotation_coverage", 0) for r in lang_runs]
                doc_dens = [r["aggregate"].get("avg_docstring_density", 0) for r in lang_runs]
                auto_patterns = {
                    "async_usage": _classify_tendency(async_ratios),
                    "type_annotations": _classify_tendency(type_covs),
                    "docstrings": _classify_tendency(doc_dens),
                }
            elif lang == "csharp":
                di_usage = [1.0 if r["aggregate"].get("uses_di") else 0.0 for r in lang_runs]
                api_ctrl = [1.0 if r["aggregate"].get("uses_api_controller") else 0.0 for r in lang_runs]
                auto_patterns = {
                    "constructor_injection": _classify_tendency(di_usage),
                    "api_controller_attr": _classify_tendency(api_ctrl),
                }
            elif lang == "java":
                ctor_inj = [1.0 if r["aggregate"].get("uses_constructor_injection") else 0.0 for r in lang_runs]
                rest_ctrl = [1.0 if r["aggregate"].get("uses_rest_controller") else 0.0 for r in lang_runs]
                valid = [1.0 if r["aggregate"].get("uses_valid_annotation") else 0.0 for r in lang_runs]
                auto_patterns = {
                    "constructor_injection": _classify_tendency(ctor_inj),
                    "rest_controller": _classify_tendency(rest_ctrl),
                    "valid_annotation": _classify_tendency(valid),
                }

            # Get consistency data
            consistency_key = f"{model}|{lang}"
            loc_cv = consistency.get(consistency_key, {}).get(
                "structural_stability", {}
            ).get("loc", {}).get("cv", 0)

            # LLM judge-derived signatures for this language
            pattern_sig = _extract_pattern_signature(lang_runs)
            idiom_prof = _extract_idiom_profile(lang_runs)
            style_sig = _extract_style_signature(lang_runs)
            error_phil = _extract_error_handling_philosophy(lang_runs, lang_runs)

            languages[lang] = {
                "n_runs": len(lang_runs),
                "avg_loc": round(avg_loc, 0),
                "avg_functions": round(avg_funcs, 1),
                "granularity": granularity,
                "loc_cv": round(loc_cv, 3),
                "automated_patterns": auto_patterns,
                "pattern_signature": pattern_sig,
                "idiom_profile": idiom_prof,
                "style_signature": style_sig,
                "error_handling": error_phil,
            }

        # Cross-language aggregates
        all_locs = [r["aggregate"].get("total_loc", 0) for r in runs]
        all_funcs = [
            r["aggregate"].get("total_functions", r["aggregate"].get("total_methods", 0))
            for r in runs
        ]

        # Cross-language judge signatures
        cross_pattern_sig = _extract_pattern_signature(runs)
        cross_style_sig = _extract_style_signature(runs)
        cross_idiom_prof = _extract_idiom_profile(runs)
        cross_error_phil = _extract_error_handling_philosophy(runs, runs)

        fingerprints[model] = {
            "model": model,
            "total_runs": len(runs),
            "languages_tested": list(by_lang.keys()),
            "per_language": languages,
            "cross_language": {
                "avg_loc": round(sum(all_locs) / len(all_locs), 0) if all_locs else 0,
                "avg_functions": round(sum(all_funcs) / len(all_funcs), 1) if all_funcs else 0,
                "loc_range": [min(all_locs), max(all_locs)] if all_locs else [0, 0],
                "pattern_signature": cross_pattern_sig,
                "style_signature": cross_style_sig,
                "idiom_profile": cross_idiom_prof,
                "error_handling": cross_error_phil,
            },
        }

    return fingerprints


# ──────────────────────────────────────────────────────────────────────
# Layer 3: Inter-Model Comparison
# ──────────────────────────────────────────────────────────────────────

def compute_inter_model_comparison(data: list[dict]) -> dict[str, Any]:
    """Compare models head-to-head within each language."""
    by_lang = defaultdict(lambda: defaultdict(list))
    for d in data:
        by_lang[d["language"]][d["model"]].append(d)

    comparisons = {}
    for lang, models in sorted(by_lang.items()):
        lang_comparison = {}
        for model, runs in sorted(models.items()):
            locs = [r["aggregate"].get("total_loc", 0) for r in runs]
            funcs = [
                r["aggregate"].get("total_functions", r["aggregate"].get("total_methods", 0))
                for r in runs
            ]
            gates = [r.get("gates_passed", 0) for r in runs]

            lang_comparison[model] = {
                "n": len(runs),
                "loc": compute_stats(locs),
                "functions": compute_stats(funcs),
                "gates": compute_stats([float(g) for g in gates]),
            }

        comparisons[lang] = lang_comparison

    return comparisons


# ──────────────────────────────────────────────────────────────────────
# Quality-Consistency Frontier (§5.2.2 of spec)
# ──────────────────────────────────────────────────────────────────────

def compute_quality_consistency_frontier(consistency: dict) -> list[dict]:
    """Compute the quality-consistency frontier data for visualization.
    
    X-axis: mean gate score (quality)
    Y-axis: gate score variance (consistency — lower is better)
    """
    points = []
    for key, data in consistency.items():
        model, language = key.split("|")
        gate_stats = data.get("gate_consistency", {}).get("gates_passed", {})
        loc_stats = data.get("structural_stability", {}).get("loc", {})

        points.append({
            "model": model,
            "language": language,
            "quality_mean": gate_stats.get("mean", 0),
            "quality_std": gate_stats.get("std", 0),
            "quality_cv": gate_stats.get("cv", 0),
            "loc_mean": loc_stats.get("mean", 0),
            "loc_cv": loc_stats.get("cv", 0),
            "n": data.get("n_runs", 0),
            "perfect_rate": data.get("gate_consistency", {}).get("perfect_rate", 0),
            "structure_consistency": data.get("fingerprint_similarity", {}).get(
                "structure_jaccard", {}
            ).get("mean", 0),
            "naming_consistency": data.get("fingerprint_similarity", {}).get(
                "naming_jaccard", {}
            ).get("mean", 0),
        })

    # Sort by quality descending
    points.sort(key=lambda x: (-x["quality_mean"], x["quality_std"]))
    return points


# ──────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────

def main():
    data = load_quality_data()
    if not data:
        print("ERROR: No quality data found. Run static_analysis.py first.")
        sys.exit(1)

    print(f"Loaded quality data for {len(data)} runs")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Layer 2: Intra-model consistency
    print("\n--- Layer 2: Intra-Model Consistency ---")
    consistency = compute_intra_model_consistency(data)
    with open(OUTPUT_DIR / "intra_model_consistency.json", "w") as f:
        json.dump(consistency, f, indent=2)
    print(f"  Computed consistency for {len(consistency)} model×language cells")

    # Print highlights
    for key, c in sorted(consistency.items(), key=lambda x: x[1]["structural_stability"]["loc"]["cv"]):
        model, lang = key.split("|")
        loc_cv = c["structural_stability"]["loc"]["cv"]
        gate_mean = c["gate_consistency"]["gates_passed"]["mean"]
        struct_j = c["fingerprint_similarity"]["structure_jaccard"]["mean"]
        name_j = c["fingerprint_similarity"]["naming_jaccard"]["mean"]
        print(f"  {model:35s} {lang:8s}  LOC CV={loc_cv:.3f}  gates={gate_mean:.1f}  struct={struct_j:.2f}  names={name_j:.2f}")

    # Layer 4: Fingerprints
    print("\n--- Layer 4: Model Fingerprints ---")
    fingerprints = extract_fingerprints(data, consistency)
    with open(OUTPUT_DIR / "model_fingerprints.json", "w") as f:
        json.dump(fingerprints, f, indent=2)
    print(f"  Extracted fingerprints for {len(fingerprints)} models")

    for model, fp in sorted(fingerprints.items()):
        langs = ", ".join(fp["languages_tested"])
        avg_loc = fp["cross_language"]["avg_loc"]
        avg_funcs = fp["cross_language"]["avg_functions"]
        cross = fp["cross_language"]
        err = cross.get("error_handling", {})
        phil = err.get("philosophy", "?")
        idiom_rate = cross.get("idiom_profile", {}).get("overall_idiomatic_rate", 0)
        quality = cross.get("style_signature", {}).get("composites", {}).get("overall_quality", {}).get("mean", 0)
        print(f"  {model:35s}  {fp['total_runs']:2d} runs  [{langs}]  "
              f"avg={avg_loc:.0f} LOC  err={phil}  idiom={idiom_rate:.0%}  quality={quality:.2f}")

    # Layer 3: Inter-model comparison
    print("\n--- Layer 3: Inter-Model Comparison ---")
    comparison = compute_inter_model_comparison(data)
    with open(OUTPUT_DIR / "inter_model_comparison.json", "w") as f:
        json.dump(comparison, f, indent=2)

    for lang, models in sorted(comparison.items()):
        print(f"\n  {lang}:")
        for model, stats in sorted(models.items(), key=lambda x: -x[1]["gates"]["mean"]):
            print(f"    {model:35s}  gates={stats['gates']['mean']:.1f}±{stats['gates']['std']:.1f}  LOC={stats['loc']['mean']:.0f}±{stats['loc']['std']:.0f}")

    # Quality-Consistency Frontier
    print("\n--- Quality-Consistency Frontier ---")
    frontier = compute_quality_consistency_frontier(consistency)
    with open(OUTPUT_DIR / "quality_consistency_frontier.json", "w") as f:
        json.dump(frontier, f, indent=2)

    print(f"  {'Model':35s} {'Lang':8s} {'Quality':>8s} {'σ':>6s} {'LOC CV':>8s} {'Struct':>7s} {'Names':>7s}")
    for p in frontier:
        quadrant = ""
        if p["quality_mean"] >= 4.5 and p["quality_cv"] <= 0.15:
            quadrant = "★ IDEAL"
        elif p["quality_mean"] >= 4.5:
            quadrant = "▲ erratic"
        elif p["quality_cv"] <= 0.15:
            quadrant = "■ mediocre"
        else:
            quadrant = "● unreliable"
        print(f"  {p['model']:35s} {p['language']:8s} {p['quality_mean']:8.1f} {p['quality_std']:6.2f} {p['loc_cv']:8.3f} {p['structure_consistency']:7.2f} {p['naming_consistency']:7.2f}  {quadrant}")

    # Summary
    summary = {
        "total_runs_analyzed": len(data),
        "model_task_cells": len(consistency),
        "models": len(fingerprints),
        "languages": list(comparison.keys()),
        "analysis_date": "2026-02-08",
        "data_source": "entropy-controlled runs only (smoke tests excluded)",
    }
    with open(OUTPUT_DIR / "quality_summary.json", "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\n✓ All analysis written to {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
