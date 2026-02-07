# Persona Prompt Optimization for LLM Evaluation Systems

**Date:** 2026-02-07  
**License:** MIT  
**Study:** [Persona Prompt Optimization Pilot Study](https://github.com/engramforge/research/tree/main/persona-prompt-optimization)

---

## Overview

This study investigates which persona prompt patterns correlate with improved
evaluation scores in a multi-dimensional LLM assessment pipeline. Eight
systematic prompt variations were tested against a baseline using automated
A/B testing infrastructure.

- **Model tested:** Claude Sonnet 4 (Anthropic API)
- **Evaluation dimensions:** 7 (accuracy, complexity, redundancy, optimization, security, understanding, experience depth)
- **Variations tested:** 8 (baseline, more_production, more_metrics, more_first_person, concise, hybrid, claude_xml, markdown_structure)
- **Runs per variation:** 2
- **Total evaluations:** 16
- **Total cost:** $0.37

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.12+ | Runtime for all scripts |
| pip | latest | Package management |
| PyYAML | ≥ 6.0 | YAML parsing for persona files |
| Anthropic API key | — | Required to run evaluations (not included) |

---

## API Keys

The following environment variables are required to run experiments:

```bash
export ANTHROPIC_API_KEY="your-key-here"
```

> **No API keys are included in this repository.** You must supply your own.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/engramforge/research.git
cd research/persona-prompt-optimization

# 2. Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
# .venv\Scripts\activate   # Windows

# 3. Install dependencies
pip install -r scripts/requirements.txt

# 4. Supply your API credentials
export ANTHROPIC_API_KEY="your-key-here"

# 5. Review baseline persona prompt
cat prompts/frontend-developer.yaml

# 6. Generate variations (dry run — no API calls)
python scripts/adaptive_persona_optimizer.py --role frontend-developer

# 7. Analyze pattern correlations (uses embedded study data)
python scripts/analyze_persona_patterns.py

# 8. Run a full variation test (requires evaluation pipeline + API key)
python scripts/test_persona_variations.py \
    --role frontend-developer \
    --questions 5 \
    --eval-cmd "python your_evaluator.py"
```

**Note:** Step 8 requires an evaluation pipeline that accepts `--role` and
`--questions-per-role` arguments and writes per-question JSON results with
a `score` field. The scripts are designed to integrate with any such pipeline.

---

## Repository Structure

```
persona-prompt-optimization/
├── README.md                                          # This file
├── data/
│   └── variation_test_results_frontend-developer_     # Raw results (JSON) for all 8
│       20260207_090630.json                           #   variations with individual run scores
├── scripts/
│   ├── requirements.txt                               # Python dependencies
│   ├── adaptive_persona_optimizer.py                  # Generates 8 systematic prompt variations
│   ├── analyze_persona_patterns.py                    # Quantifies prompt features and correlations
│   └── test_persona_variations.py                     # Automated A/B test harness
├── prompts/
│   ├── frontend-developer.yaml                        # Baseline persona (score: 67.6 ± 5.2)
│   └── frontend-developer-hybrid.yaml                 # Winning hybrid persona (score: 72.3 ± 1.5)
└── diagrams/
    ├── testing_framework_architecture.svg             # Pipeline architecture diagram
    └── variation_results_comparison.svg               # Results comparison bar chart
```

---

## How It Works

### Variation Generation

`adaptive_persona_optimizer.py` takes a baseline persona YAML and generates
7 systematic variations, each targeting a different content pattern:

| Variation | Strategy |
|-----------|----------|
| baseline | Unmodified production prompt |
| more_production | Inject production/deployment scenarios |
| more_metrics | Add quantified improvements (99.9% uptime, etc.) |
| more_first_person | Increase first-person language ("I've built…") |
| concise | Remove filler words and compress sentences |
| hybrid | Combine production scenarios + quantified metrics |
| claude_xml | Add XML tag structure hints |
| markdown_structure | Add markdown formatting instructions |

### A/B Testing

`test_persona_variations.py` iterates through each variation:

1. Backs up the original persona YAML
2. Applies the variation
3. Invokes the evaluation pipeline (configurable via `--eval-cmd`)
4. Collects scores, token usage, cost, and timing
5. Restores the original persona
6. Saves all results to a timestamped JSON file

### Pattern Analysis

`analyze_persona_patterns.py` quantifies prompt features (first-person
phrases, production terms, lesson-learned phrases, metrics, section headers,
word count) and compares averages across successful vs. unsuccessful
optimizations.

### Scoring

Each evaluation response is scored across 7 dimensions (0–100 each),
then combined via weighted averaging into a composite score. All scores
reported include mean ± standard deviation with sample sizes.

---

## Data Format

Results are stored in `data/` as JSON arrays. Each entry:

```json
{
  "variation": "hybrid",
  "status": "success",
  "avg_score": 72.26,
  "min_score": 71.20,
  "max_score": 73.31,
  "sample_count": 2,
  "total_cost": 0.0469,
  "elapsed_time": 60.79,
  "model": "unknown",
  "tokens": {
    "input": 0,
    "output": 0,
    "thinking": 342,
    "total": 342
  },
  "tokens_per_sec": {
    "total": 5.63,
    "input": 0.0,
    "output": 0.0
  }
}
```

| Field | Description |
|-------|-------------|
| `variation` | Name of the prompt variation tested |
| `status` | `success`, `failed`, `timeout`, or `error` |
| `avg_score` | Mean composite score across all runs |
| `min_score` / `max_score` | Range of individual run scores |
| `sample_count` | Number of evaluation runs (n) |
| `total_cost` | API cost in USD for this variation |
| `elapsed_time` | Wall-clock time in seconds |
| `model` | Model identifier used |
| `tokens` | Token breakdown (input, output, thinking) |
| `tokens_per_sec` | Throughput metrics |

---

## Key Findings

| Variation | Mean ± Std | Δ vs Baseline | Cost | n |
|-----------|-----------|---------------|------|---|
| **hybrid** | **72.3 ± 1.5** | **+4.6** | $0.047 | 2 |
| concise | 70.7 ± 0.2 | +3.1 | $0.047 | 2 |
| more_production | 70.5 ± 1.1 | +2.9 | $0.044 | 2 |
| more_metrics | 69.9 ± 1.5 | +2.3 | $0.044 | 2 |
| more_first_person | 69.5 ± 3.6 | +1.9 | $0.049 | 2 |
| baseline | 67.6 ± 5.2 | — | $0.046 | 2 |
| claude_xml | 67.6 ± 6.5 | 0.0 | $0.042 | 2 |
| markdown_structure | 66.2 ± 1.7 | −1.4 | $0.046 | 2 |

**Key observations:**
1. Hybrid (production scenarios + quantified metrics) scored highest at 72.3 ± 1.5
2. Content patterns outperformed syntax preferences in this evaluation context
3. Model-specific XML tags provided no measurable benefit (same mean as baseline, higher variance)
4. Markdown structure instructions decreased performance (−1.4 points)

**Limitations:** n=2 per variation limits statistical confidence. Results are
specific to Claude Sonnet 4 and our evaluation pipeline configuration.

---

## Citation

If you use this methodology or data, please cite:

```
EngramForge (2026). Persona Prompt Optimization for LLM Evaluation Systems:
A Systems Engineering Approach to Empirical Prompt Testing.
https://github.com/engramforge/research/tree/main/persona-prompt-optimization
```

---

## License

MIT — see [LICENSE](../LICENSE) for details.
