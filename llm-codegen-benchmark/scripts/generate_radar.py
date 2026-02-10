#!/usr/bin/env python3
"""Generate fingerprint radar SVG from model_fingerprints.json data.

Reads:  pilot/results/quality_analysis/model_fingerprints.json
        pilot/results/quality_analysis/intra_model_consistency.json
Writes: diagrams/fingerprint-radar.svg

Radar axes (7 dimensions):
  1. GateQ        — mean gate pass rate (0–5 → 0–1)
  2. Consistency   — 1 - mean LOC CV (lower CV = higher consistency)
  3. Structure     — mean structure Jaccard similarity
  4. Naming        — mean naming Jaccard similarity
  5. Quality       — overall_quality composite (0–5 → 0–1)
  6. Idiom         — overall_idiomatic_rate (0–1)
  7. ErrorHandling — error_handling score (1–5 → 0–1)
"""

import json
import math
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results" / "quality_analysis"
OUTPUT = Path(__file__).resolve().parent.parent / "diagrams" / "fingerprint-radar.svg"

# Models to show (pick representative spread, not all 11)
DISPLAY_MODELS = [
    "gemini:gemini-3-pro-preview",
    "claude-sonnet-4.5",
    "gpt-4o",
    "gpt-4o-mini",
    "cloud:deepseek-v3.2",
]

# Colors for each model
MODEL_COLORS = {
    "gemini:gemini-3-pro-preview": ("#2A8F82", "rgba(42,143,130,0.12)"),
    "claude-sonnet-4.5": ("#C0392B", "rgba(192,57,43,0.10)"),
    "gpt-4o": ("#4A6FA5", "rgba(74,111,165,0.10)"),
    "gpt-4o-mini": ("#F5A623", "rgba(245,166,35,0.10)"),
    "cloud:deepseek-v3.2": ("#8B5CF6", "rgba(139,92,246,0.10)"),
}

SHORT_NAMES = {
    "gemini:gemini-3-pro-preview": "Gemini 3 Pro",
    "claude-sonnet-4.5": "Claude Sonnet 4.5",
    "gpt-4o": "GPT-4o",
    "gpt-4o-mini": "GPT-4o-mini",
    "cloud:deepseek-v3.2": "DeepSeek V3.2",
}

AXES = ["GateQ", "Consistency", "Structure", "Naming", "Quality", "Idiom", "ErrorH"]
N_AXES = len(AXES)
CX, CY = 310, 310  # radar center (shifted left for legend panel)
RADIUS = 200


def load_fingerprint_values(model: str, fingerprints: dict, consistency: dict) -> list[float]:
    """Extract 7 normalized values (0–1) for the radar axes."""
    fp = fingerprints.get(model)
    if not fp:
        return [0.0] * N_AXES

    # GateQ: average gate pass rate across all cells for this model
    gate_scores = []
    for key, data in consistency.items():
        m, _lang = key.split("|")
        if m == model:
            gate_scores.append(data["gate_consistency"]["gates_passed"]["mean"])
    gate_q = (sum(gate_scores) / len(gate_scores) / 5.0) if gate_scores else 0

    # Consistency: 1 - mean LOC CV (clamped, log-ish scale)
    # CV=0 → 1.0, CV=0.05 → 0.85, CV=0.1 → 0.70, CV=0.2 → 0.40, CV=0.4 → 0.0
    loc_cvs = []
    for key, data in consistency.items():
        m, _lang = key.split("|")
        if m == model:
            loc_cvs.append(data["structural_stability"]["loc"]["cv"])
    mean_cv = sum(loc_cvs) / len(loc_cvs) if loc_cvs else 0
    consistency_val = max(0, 1.0 - mean_cv * 2.5)  # CV=0→1.0, CV=0.4→0.0

    # Structure: mean structure Jaccard
    struct_js = []
    for key, data in consistency.items():
        m, _lang = key.split("|")
        if m == model:
            struct_js.append(data["fingerprint_similarity"]["structure_jaccard"]["mean"])
    structure = sum(struct_js) / len(struct_js) if struct_js else 0

    # Naming: mean naming Jaccard
    name_js = []
    for key, data in consistency.items():
        m, _lang = key.split("|")
        if m == model:
            name_js.append(data["fingerprint_similarity"]["naming_jaccard"]["mean"])
    naming = sum(name_js) / len(name_js) if name_js else 0

    # Quality: overall_quality composite from judge (0–5 → 0–1)
    cross = fp.get("cross_language", {})
    quality_mean = (
        cross.get("style_signature", {})
        .get("composites", {})
        .get("overall_quality", {})
        .get("mean", 0)
    )
    quality = quality_mean / 5.0

    # Idiom: overall idiomatic rate (already 0–1)
    idiom = cross.get("idiom_profile", {}).get("overall_idiomatic_rate", 0)

    # Error handling: score mean (1–5 → 0–1)
    err_mean = (
        cross.get("error_handling", {}).get("score_stats", {}).get("mean", 0)
    )
    error_h = err_mean / 5.0

    return [gate_q, consistency_val, structure, naming, quality, idiom, error_h]


def polar_point(axis_index: int, value: float) -> tuple[float, float]:
    """Convert axis index + value (0–1) to SVG x,y coordinates."""
    angle = (2 * math.pi * axis_index / N_AXES) - math.pi / 2  # start from top
    r = value * RADIUS
    return CX + r * math.cos(angle), CY + r * math.sin(angle)


def _model_stats(model: str, fingerprints: dict, consistency: dict) -> dict:
    """Compute display stats for a model's legend entry."""
    gates, gate_stds = [], []
    for key, data in consistency.items():
        m, _lang = key.split("|")
        if m == model:
            gates.append(data["gate_consistency"]["gates_passed"]["mean"])
            gate_stds.append(data["gate_consistency"]["gates_passed"]["std"])
    avg_gate = sum(gates) / len(gates) if gates else 0
    avg_std = sum(gate_stds) / len(gate_stds) if gate_stds else 0

    fp = fingerprints.get(model, {})
    cross = fp.get("cross_language", {})
    quality = cross.get("style_signature", {}).get("composites", {}).get("overall_quality", {}).get("mean", 0)
    idiom = cross.get("idiom_profile", {}).get("overall_idiomatic_rate", 0)
    err_phil = cross.get("error_handling", {}).get("philosophy", "?")

    return {
        "gate": avg_gate,
        "gate_std": avg_std,
        "quality": quality,
        "idiom": idiom,
        "error_phil": err_phil,
    }


def generate_svg(fingerprints: dict, consistency: dict) -> str:
    lines = []
    W, H = 880, 640
    LEGEND_X = 580  # left edge of legend panel

    lines.append(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}"'
                 f' font-family="-apple-system, BlinkMacSystemFont, \'Segoe UI\','
                 f' Roboto, Helvetica, Arial, sans-serif">')
    lines.append(f'  <rect width="{W}" height="{H}" fill="#FFFFFF"/>')

    # Title
    lines.append(f'  <text x="{CX}" y="32" text-anchor="middle" font-size="18"'
                 f' font-weight="600" fill="#1A1A2E">Model Generation Fingerprints</text>')
    lines.append(f'  <text x="{CX}" y="50" text-anchor="middle" font-size="11"'
                 f' fill="#8B8FA3">{N_AXES} dimensions — {len(DISPLAY_MODELS)} models'
                 f' — 165 entropy-controlled runs</text>')

    # Grid rings
    for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
        pts = " ".join(f"{polar_point(i, frac)[0]:.1f},{polar_point(i, frac)[1]:.1f}"
                       for i in range(N_AXES))
        alpha = "0.4" if frac == 1.0 else "0.15"
        lines.append(f'  <polygon points="{pts}" fill="none" stroke="#D0D0D0"'
                     f' stroke-width="0.75" opacity="{alpha}"/>')

    # Scale labels on first axis
    for frac in (0.2, 0.4, 0.6, 0.8, 1.0):
        px, py = polar_point(0, frac)
        lines.append(f'  <text x="{px + 4:.1f}" y="{py - 4:.1f}" font-size="8"'
                     f' fill="#AAAAAA">{frac:.1f}</text>')

    # Axis lines + labels
    for i, label in enumerate(AXES):
        px, py = polar_point(i, 1.0)
        lines.append(f'  <line x1="{CX}" y1="{CY}" x2="{px:.1f}" y2="{py:.1f}"'
                     f' stroke="#D0D0D0" stroke-width="0.75"/>')
        lx, ly = polar_point(i, 1.15)
        anchor = "middle"
        if lx < CX - 10:
            anchor = "end"
        elif lx > CX + 10:
            anchor = "start"
        lines.append(f'  <text x="{lx:.1f}" y="{ly:.1f}" text-anchor="{anchor}"'
                     f' font-size="11" font-weight="600" fill="#1A1A2E">{label}</text>')

    # Model polygons
    for model in DISPLAY_MODELS:
        color, fill_color = MODEL_COLORS.get(model, ("#555", "rgba(85,85,85,0.1)"))
        values = load_fingerprint_values(model, fingerprints, consistency)
        pts = " ".join(f"{polar_point(i, v)[0]:.1f},{polar_point(i, v)[1]:.1f}"
                       for i, v in enumerate(values))
        lines.append(f'  <polygon points="{pts}" fill="{fill_color}"'
                     f' stroke="{color}" stroke-width="2"/>')
        for i, v in enumerate(values):
            px, py = polar_point(i, v)
            lines.append(f'  <circle cx="{px:.1f}" cy="{py:.1f}" r="3"'
                         f' fill="{color}"/>')

    # ── Legend: Models table ──────────────────────────────────
    table_y = 70
    table_w = 272
    row_h = 22
    header_h = 24
    n_rows = len(DISPLAY_MODELS)
    table_h = header_h + n_rows * row_h + 10

    lines.append(f'  <rect x="{LEGEND_X}" y="{table_y}" width="{table_w}"'
                 f' height="{table_h}" rx="6" fill="#FFFFFF" stroke="#E0E0E0" stroke-width="1"/>')
    lines.append(f'  <text x="{LEGEND_X + table_w // 2}" y="{table_y + 16}"'
                 f' text-anchor="middle" font-size="11" font-weight="600" fill="#1A1A2E">'
                 f'Models (all languages)</text>')
    lines.append(f'  <line x1="{LEGEND_X + 8}" y1="{table_y + header_h}"'
                 f' x2="{LEGEND_X + table_w - 8}" y2="{table_y + header_h}"'
                 f' stroke="#E8E8E8" stroke-width="1"/>')

    # Column headers
    ch_y = table_y + header_h + 12
    lines.append(f'  <text x="{LEGEND_X + 24}" y="{ch_y}" font-size="7"'
                 f' font-weight="600" fill="#8B8FA3">Model</text>')
    lines.append(f'  <text x="{LEGEND_X + 136}" y="{ch_y}" font-size="7"'
                 f' font-weight="600" fill="#8B8FA3">Gates</text>')
    lines.append(f'  <text x="{LEGEND_X + 176}" y="{ch_y}" font-size="7"'
                 f' font-weight="600" fill="#8B8FA3">Quality</text>')
    lines.append(f'  <text x="{LEGEND_X + 218}" y="{ch_y}" font-size="7"'
                 f' font-weight="600" fill="#8B8FA3">Idiom</text>')
    lines.append(f'  <text x="{LEGEND_X + 250}" y="{ch_y}" font-size="7"'
                 f' font-weight="600" fill="#8B8FA3">Err</text>')

    for j, model in enumerate(DISPLAY_MODELS):
        color, _ = MODEL_COLORS.get(model, ("#555", ""))
        short = SHORT_NAMES.get(model, model)
        stats = _model_stats(model, fingerprints, consistency)
        ry = ch_y + 6 + j * row_h

        # Color swatch
        lines.append(f'  <rect x="{LEGEND_X + 10}" y="{ry - 1}" width="10"'
                     f' height="10" rx="2" fill="{color}"/>')
        # Model name
        lines.append(f'  <text x="{LEGEND_X + 24}" y="{ry + 8}" font-size="9"'
                     f' fill="#1A1A2E">{short}</text>')
        # Gates
        lines.append(f'  <text x="{LEGEND_X + 136}" y="{ry + 8}" font-size="8"'
                     f' fill="#555">{stats["gate"]:.1f}/5</text>')
        # Quality
        lines.append(f'  <text x="{LEGEND_X + 176}" y="{ry + 8}" font-size="8"'
                     f' fill="#555">{stats["quality"]:.2f}</text>')
        # Idiom
        lines.append(f'  <text x="{LEGEND_X + 218}" y="{ry + 8}" font-size="8"'
                     f' fill="#555">{stats["idiom"]:.0%}</text>')
        # Error philosophy (abbreviate)
        err_abbrev = {"defensive": "def", "pragmatic": "prag",
                      "minimal": "min", "optimistic": "opt"}
        lines.append(f'  <text x="{LEGEND_X + 250}" y="{ry + 8}" font-size="8"'
                     f' fill="#555">{err_abbrev.get(stats["error_phil"], stats["error_phil"])}</text>')

    # ── Key Findings box ─────────────────────────────────────
    findings_y = table_y + table_h + 16
    findings_h = 130
    lines.append(f'  <rect x="{LEGEND_X}" y="{findings_y}" width="{table_w}"'
                 f' height="{findings_h}" rx="6" fill="#FFF8E1" stroke="#F5A623" stroke-width="1"/>')
    lines.append(f'  <text x="{LEGEND_X + 12}" y="{findings_y + 18}" font-size="10"'
                 f' font-weight="600" fill="#E09600">Key Findings</text>')

    findings = [
        "Gemini 3 Pro: only model with 5.0/5 gates",
        "Sonnet 4.5: highest consistency (0.98)",
        "GPT-4o: top quality (4.28) despite LOC variance",
        "DeepSeek: highest idiom (85%) but lowest quality",
        "4o-mini: clean code but weak gates (3.6/5)",
        "Error handling weakest dimension across all",
    ]
    for k, finding in enumerate(findings):
        fy = findings_y + 36 + k * 15
        lines.append(f'  <text x="{LEGEND_X + 12}" y="{fy}" font-size="8"'
                     f' fill="#555">{finding}</text>')

    # ── Axis key (below findings) ────────────────────────────
    akey_y = findings_y + findings_h + 16
    akey_h = 116
    lines.append(f'  <rect x="{LEGEND_X}" y="{akey_y}" width="{table_w}"'
                 f' height="{akey_h}" rx="6" fill="#F5F5F5" stroke="#E0E0E0" stroke-width="1"/>')
    lines.append(f'  <text x="{LEGEND_X + 12}" y="{akey_y + 16}" font-size="9"'
                 f' font-weight="600" fill="#1A1A2E">Axis Definitions</text>')

    axis_defs = [
        ("GateQ", "Mean gate pass rate (0\u20135 \u2192 0\u20131)"),
        ("Consistency", "1 \u2212 LOC CV (lower variance = higher)"),
        ("Structure", "Jaccard similarity of code structure"),
        ("Naming", "Jaccard similarity of identifiers"),
        ("Quality", "LLM-judged composite (0\u20135 \u2192 0\u20131)"),
        ("Idiom", "Framework idiom adherence rate"),
        ("ErrorH", "Error handling score (1\u20135 \u2192 0\u20131)"),
    ]
    for k, (ax_name, ax_desc) in enumerate(axis_defs):
        ay = akey_y + 32 + k * 12
        lines.append(f'  <text x="{LEGEND_X + 12}" y="{ay}" font-size="7"'
                     f' font-weight="600" fill="#555">{ax_name}</text>')
        lines.append(f'  <text x="{LEGEND_X + 72}" y="{ay}" font-size="7"'
                     f' fill="#888">{ax_desc}</text>')

    # Footer
    lines.append(f'  <text x="{W // 2}" y="{H - 10}" text-anchor="middle"'
                 f' font-size="9" fill="#8B8FA3">'
                 f'Outer ring = 1.0 (best)  \u2022  Center = 0.0 (worst)  \u2022'
                 f'  Data from model_fingerprints.json + intra_model_consistency.json</text>')

    lines.append('</svg>')
    return "\n".join(lines)


def main():
    fp_file = RESULTS_DIR / "model_fingerprints.json"
    con_file = RESULTS_DIR / "intra_model_consistency.json"

    if not fp_file.exists() or not con_file.exists():
        print("ERROR: Run quality_analysis.py first to generate data files.")
        sys.exit(1)

    fingerprints = json.load(open(fp_file))
    consistency = json.load(open(con_file))

    # Print values for verification
    print("Radar values (0–1):")
    print(f"  {'Model':35s} " + " ".join(f"{a:>8s}" for a in AXES))
    for model in DISPLAY_MODELS:
        values = load_fingerprint_values(model, fingerprints, consistency)
        vals_str = " ".join(f"{v:8.3f}" for v in values)
        short = SHORT_NAMES.get(model, model)
        print(f"  {short:35s} {vals_str}")

    svg = generate_svg(fingerprints, consistency)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(svg)
    print(f"\n✓ Wrote {OUTPUT}")


if __name__ == "__main__":
    main()
