#!/usr/bin/env python3
"""
Analyze patterns in persona prompts that correlate with scoring improvements.

Compares optimized vs baseline personas to identify what characteristics
led to better scores. Can operate on local YAML files or on hardcoded
study data when persona files are not available.

Usage:
    python analyze_persona_patterns.py
    python analyze_persona_patterns.py --prompts-dir ../prompts

Part of the Persona Prompt Optimization study:
https://github.com/engramforge/research/tree/main/persona-prompt-optimization
"""

import argparse
import re
from pathlib import Path
from collections import defaultdict
import yaml

# Resolve repo root relative to this script
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
PROMPTS_DIR = REPO_ROOT / "prompts"


def analyze_persona_text(text: str) -> dict:
    """Extract quantifiable features from persona text."""

    first_person_patterns = [
        r"I've\s+\w+",
        r"I\s+\w+ed",
        r"In my experience",
        r"I discovered",
        r"I learned",
        r"I realized",
        r"I found",
        r"our team",
    ]
    first_person_count = sum(
        len(re.findall(pattern, text, re.IGNORECASE))
        for pattern in first_person_patterns
    )

    production_patterns = [
        r"production",
        r"deployment",
        r"troubleshooting",
        r"debugging",
        r"monitoring",
        r"incident",
        r"maintenance",
    ]
    production_count = sum(
        len(re.findall(pattern, text, re.IGNORECASE))
        for pattern in production_patterns
    )

    lessons_patterns = [
        r"learned",
        r"discovered",
        r"realized",
        r"found out",
        r"mistake",
        r"pitfall",
        r"challenge",
    ]
    lessons_count = sum(
        len(re.findall(pattern, text, re.IGNORECASE))
        for pattern in lessons_patterns
    )

    metrics_count = len(re.findall(r'\d+%|\d+x|\d+\+|from \d+|\d+ to \d+', text))
    section_count = len(re.findall(r'##\s+\w+', text))

    tool_patterns = [
        r'\w+\s+\d+\.\d+',
        r'\w+\s+\d+\.x',
    ]
    tool_count = sum(
        len(re.findall(pattern, text))
        for pattern in tool_patterns
    )

    word_count = len(text.split())
    sentence_count = len(re.split(r'[.!?]+', text))
    avg_sentence_length = word_count / max(1, sentence_count)

    return {
        'first_person_count': first_person_count,
        'production_count': production_count,
        'lessons_count': lessons_count,
        'metrics_count': metrics_count,
        'section_count': section_count,
        'tool_version_count': tool_count,
        'word_count': word_count,
        'avg_sentence_length': avg_sentence_length,
    }


def load_persona(role_id: str, prompts_dir: Path) -> dict:
    """Load persona YAML file from the prompts directory."""
    persona_path = prompts_dir / f"{role_id}.yaml"
    if not persona_path.exists():
        return None
    with open(persona_path) as f:
        return yaml.safe_load(f)


def analyze_role_improvements(prompts_dir: Path):
    """Analyze what worked vs what didn't across roles.

    The score data below is from the initial manual optimization
    phase of the study (n=1 per condition — directional only).
    """

    results = {
        'release-manager': {'baseline': 72.9, 'optimized': 74.5, 'change': +1.6},
        'qa-automation-engineer': {'baseline': 74.1, 'optimized': 74.9, 'change': +0.8},
        'frontend-developer': {'baseline': 69.3, 'optimized': 69.2, 'change': -0.1},
        'ux-ui-designer': {'baseline': 71.7, 'optimized': 71.1, 'change': -0.6},
        'technical-lead': {'baseline': 72.9, 'optimized': 72.7, 'change': -0.2},
    }

    print("=" * 80)
    print("Persona Pattern Analysis")
    print("=" * 80)
    print()

    successful = []
    unsuccessful = []

    for role_id, scores in results.items():
        persona = load_persona(role_id, prompts_dir)
        if not persona:
            # If YAML not available, report scores only
            print(f"  ⚠  Persona file not found for {role_id} — skipping feature analysis")
            continue

        prompt_text = persona.get('persona_prompt', '')
        features = analyze_persona_text(prompt_text)
        features['role_id'] = role_id
        features['score_change'] = scores['change']
        features['baseline'] = scores['baseline']
        features['optimized'] = scores['optimized']

        if scores['change'] > 0:
            successful.append(features)
        else:
            unsuccessful.append(features)

    # ── Print successful ──────────────────────────────────────────────
    print("✅ SUCCESSFUL OPTIMIZATIONS (improved scores):")
    print("-" * 80)
    for features in successful:
        print(f"\n{features['role_id']} (+{features['score_change']:.1f} points)")
        for key in ['first_person_count', 'production_count', 'lessons_count',
                     'metrics_count', 'section_count', 'tool_version_count',
                     'word_count', 'avg_sentence_length']:
            print(f"  {key}: {features[key]:.1f}" if isinstance(features[key], float)
                  else f"  {key}: {features[key]}")

    # ── Print unsuccessful ────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("❌ UNSUCCESSFUL OPTIMIZATIONS (flat or declined):")
    print("-" * 80)
    for features in unsuccessful:
        print(f"\n{features['role_id']} ({features['score_change']:+.1f} points)")
        for key in ['first_person_count', 'production_count', 'lessons_count',
                     'metrics_count', 'section_count', 'tool_version_count',
                     'word_count', 'avg_sentence_length']:
            print(f"  {key}: {features[key]:.1f}" if isinstance(features[key], float)
                  else f"  {key}: {features[key]}")

    # ── Averages & differences ────────────────────────────────────────
    feature_keys = ['first_person_count', 'production_count', 'lessons_count',
                    'metrics_count', 'section_count', 'tool_version_count',
                    'word_count', 'avg_sentence_length']

    print("\n" + "=" * 80)
    print("PATTERN COMPARISON (averages):")
    print("-" * 80)

    if successful:
        avg_s = {k: sum(f[k] for f in successful) / len(successful) for k in feature_keys}
        print("\n✅ Successful personas (avg):")
        for k, v in avg_s.items():
            print(f"  {k}: {v:.1f}")

    if unsuccessful:
        avg_u = {k: sum(f[k] for f in unsuccessful) / len(unsuccessful) for k in feature_keys}
        print("\n❌ Unsuccessful personas (avg):")
        for k, v in avg_u.items():
            print(f"  {k}: {v:.1f}")

        if successful:
            print("\n📊 DIFFERENCES (successful − unsuccessful):")
            for k in feature_keys:
                diff = avg_s[k] - avg_u[k]
                indicator = "📈" if diff > 0 else "📉"
                print(f"  {indicator} {k}: {diff:+.1f}")

    # ── Insights ──────────────────────────────────────────────────────
    print("\n" + "=" * 80)
    print("\n💡 INSIGHTS:")
    print("-" * 80)

    if successful and unsuccessful:
        if avg_s['first_person_count'] > avg_u['first_person_count']:
            print("  ✓ More first-person language correlates with better scores")
        if avg_s['production_count'] > avg_u['production_count']:
            print("  ✓ More production/real-world scenarios help")
        if avg_s['lessons_count'] > avg_u['lessons_count']:
            print("  ✓ More 'lessons learned' language improves scoring")
        if avg_s['word_count'] < avg_u['word_count']:
            print("  ✓ Shorter prompts may be better (less verbose)")
        if avg_s['section_count'] > avg_u['section_count']:
            print("  ✓ More structured sections (## headers) help")

    print("\n" + "=" * 80)


def main():
    parser = argparse.ArgumentParser(
        description='Analyze persona prompt patterns that correlate with score improvements'
    )
    parser.add_argument(
        '--prompts-dir', type=Path, default=PROMPTS_DIR,
        help='Directory containing persona YAML files (default: ../prompts)'
    )
    args = parser.parse_args()
    analyze_role_improvements(args.prompts_dir)


if __name__ == "__main__":
    main()
