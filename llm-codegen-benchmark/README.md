# LLM Code Generation Benchmark — Supporting Code & Data

**Study:** Measuring LLM Code Generation Consistency for Platform Integration  
**Date:** 2026-02-07  
**License:** MIT

---

## Overview

This directory contains the raw data, reproduction scripts, prompt templates, baseline source code, and task definitions from a pilot study on LLM code generation quality across enterprise frameworks.

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
├── baselines/
│   ├── fastapi/                        # Python baseline source code
│   │   ├── app/main.py
│   │   ├── app/dependencies/auth.py
│   │   ├── app/routers/__init__.py
│   │   └── tests/conftest.py
│   ├── aspnetcore/                     # C# baseline source code
│   │   └── src/BenchApi/
│   │       ├── BenchApi.csproj
│   │       ├── Program.cs
│   │       └── Services/UserService.cs
│   └── springboot/                     # Java baseline source code
│       ├── pom.xml
│       └── src/main/java/com/benchmark/
│           ├── BenchApplication.java
│           └── service/UserService.java
└── diagrams/
    ├── benchmark-pipeline.svg          # Pipeline architecture diagram
    └── entropy-control-flow.svg        # Entropy control decision flow
```

## Quick Start

### Inspect the data

```bash
# Summary statistics (15 model×task combinations)
python3 -c "
import json
for r in json.load(open('data/summary_statistics.json')):
    print(f\"{r['model']:20s} | {r['task']:18s} | {r['mean_gates']:.2f} ± {r['std_gates']:.2f} | n={r['n']}\")
"

# Individual run scores as CSV
head -5 data/entropy_controlled_runs.csv
```

### Reproduce the study

To reproduce these results you need:

1. **API keys** for OpenAI and/or Anthropic (not included)
2. **The baseline codebases** (included in `baselines/`)
3. **The prompt templates** (included in `prompts/`)
4. **The task definitions** (included in `tasks/`)
5. **A benchmark runner** — the `scripts/entropy_control.py` module provides the variance detection and re-run logic; you'll need to write a harness that:
   - Assembles a prompt from the template + baseline files
   - Sends it to an LLM API
   - Extracts file blocks from the response
   - Applies changes to a copy of the baseline
   - Runs tests, type-checking, and linting
   - Feeds results into `EntropyController.should_continue()`

```python
from scripts.entropy_control import EntropyController

controller = EntropyController(min_confidence=0.85, max_runs=5)
results = []

while controller.should_continue(results):
    result = your_benchmark_function(model, task)
    results.append(result)

stats = controller.get_statistics(results)
print(f"Gates: {stats['quality_mean']:.2f} ± {stats['quality_std']:.2f}")
```

### Quality gates

Each benchmark run scores 0–5 based on sequential quality gates:

| Gate | Tool (FastAPI) | Tool (ASP.NET) | Tool (Spring Boot) |
|------|---------------|----------------|-------------------|
| 1. Diff Extraction | Custom parser | Custom parser | Custom parser |
| 2. Diff Application | file writer | file writer | file writer |
| 3. Tests | pytest | xUnit | Maven Surefire |
| 4. Type Check | mypy | Roslyn | javac |
| 5. Lint | ruff | Roslyn analyzers | Checkstyle |

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

## Key Findings

| Model | Mean Gates (All Tasks) | Variance | Cost/Run |
|-------|----------------------|----------|----------|
| Claude Sonnet 4.5 | 5.00 ± 0.00 | None | $0.043 |
| GPT-4o | 4.89 ± 0.33 | Low | $0.016 |
| Claude Opus 4.6 | 4.67 ± 0.47 | Low | $0.282 |
| GPT-4o-mini | 4.33 ± 1.25 | High on Python | $0.001 |
| GPT-5.2 | 4.00 ± 1.63 | High on Python | $0.026 |

## Citation

If you find this methodology or data useful:

```
EngramForge Engineering. "Measuring LLM Code Generation Consistency
for Platform Integration." February 2026.
https://github.com/engramforge/research/tree/main/llm-codegen-benchmark
```
