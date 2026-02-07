# LLM Code Generation Benchmark — Supporting Code & Data

**Published study:** [Measuring LLM Code Generation Consistency for Platform Integration](https://github.com/engramforge/llm-codebench/blob/main/LLM_CODEGEN_PILOT_STUDY.md)  
**Project:** [engramforge/llm-codebench](https://github.com/engramforge/llm-codebench)  
**Date:** February 2026  
**License:** MIT

---

## Overview

This directory contains the raw data, reproduction scripts, prompt templates, and task definitions supporting the pilot study on LLM code generation quality across enterprise frameworks.

The study measured five commercial LLMs (Claude Sonnet 4.5, GPT-4o, Claude Opus 4.6, GPT-4o-mini, GPT-5.2) against a standardized brownfield task across three frameworks (Python/FastAPI, C#/ASP.NET Core 9, Java/Spring Boot 3), using entropy-controlled multi-run testing.

## Contents

```
llm-codegen-benchmark/
├── README.md                           ← this file
├── data/
│   ├── entropy_controlled_runs.json    # All 48 individual run results
│   ├── entropy_controlled_runs.csv     # Same data in CSV format
│   └── summary_statistics.json         # Aggregated mean ± std per model×task
├── scripts/
│   └── entropy_control.py              # Variance detection and re-run logic
├── prompts/
│   ├── fastapi.txt                     # Python/FastAPI prompt template
│   ├── aspnetcore.txt                  # C#/ASP.NET Core prompt template
│   └── springboot.txt                  # Java/Spring Boot prompt template
├── tasks/
│   ├── fastapi-001.yaml                # FastAPI task definition
│   ├── aspnetcore-001.yaml             # ASP.NET Core task definition
│   └── springboot-001.yaml             # Spring Boot task definition
└── diagrams/
    ├── benchmark-pipeline.svg          # Pipeline architecture diagram
    └── entropy-control-flow.svg        # Entropy control decision flow
```

## Quick Start

### Inspect the data

```bash
# Summary statistics (15 model×task combinations)
python3 -c "import json; [print(f\"{r['model']:20s} | {r['task']:18s} | {r['mean_gates']:.2f} ± {r['std_gates']:.2f} | n={r['n']}\") for r in json.load(open('data/summary_statistics.json'))]"

# Individual run scores as CSV
head -5 data/entropy_controlled_runs.csv
```

### Reproduce the benchmark

The full benchmark runner is in the [llm-codebench](https://github.com/engramforge/llm-codebench) repository:

```bash
git clone https://github.com/engramforge/llm-codebench.git
cd llm-codebench/pilot
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Set API keys (not included — use your own)
export OPENAI_API_KEY="your-key"
export ANTHROPIC_API_KEY="your-key"

# Run a single entropy-controlled benchmark
python run_benchmark.py \
  --model claude-sonnet-4.5 \
  --task fastapi-001 \
  --entropy-control \
  --min-confidence 0.85 \
  --max-entropy-runs 5
```

## Data Format

### entropy_controlled_runs.json

Each entry represents one benchmark run:

```json
{
  "model": "claude-sonnet-4.5",
  "task": "fastapi-001",
  "timestamp": "20260207-085932",
  "gates": {
    "diff_extracted": true,
    "diff_applied": true,
    "tests_passed": true,
    "mypy_passed": true,
    "ruff_passed": true
  },
  "gates_passed": 5,
  "input_tokens": 1371,
  "output_tokens": 1073,
  "total_tokens": 2444,
  "estimated_cost_usd": 0.023576,
  "tests_total": 7,
  "tests_failed": 0,
  "mypy_errors": 0,
  "ruff_errors": 0
}
```

### summary_statistics.json

Aggregated per model×task combination:

```json
{
  "model": "gpt-4o-mini",
  "task": "fastapi-001",
  "n": 16,
  "mean_gates": 2.06,
  "std_gates": 1.69,
  "confidence": 18.0,
  "perfect_rate": 18.8,
  "cost_per_run_usd": 0.0005,
  "individual_scores": [2, 2, 5, 2, 5, 2, 2, 2, 5, 2, 2, 2, 2, 2, 0, 2]
}
```

## Citation

If you find this methodology or data useful, please link to the published study:

```
EngramForge Engineering. "Measuring LLM Code Generation Consistency
for Platform Integration." February 2026.
https://github.com/engramforge/llm-codebench/blob/main/LLM_CODEGEN_PILOT_STUDY.md
```
