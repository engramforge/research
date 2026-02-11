# LLM Code Generation Benchmark — Reproduction Package

**Study:** Measuring LLM Code Generation Consistency for Platform Integration  
**Date:** 2026-02-11  
**License:** MIT

---

## Overview

This repository contains everything needed to reproduce our pilot study on LLM code generation quality across enterprise frameworks. It is fully self-contained — no external repositories are required.

The study measured **11 LLMs from four providers** against a standardized brownfield task ("add an Orders endpoint") across three frameworks, using entropy-controlled multi-run testing (n=5 per cell, temperature=0.2) to detect variance that single-run benchmarks miss. The study also includes a meta-prompting experiment (prompt format preference discovery + A/B testing) and a code quality meta-analysis using cross-family LLM judges.

**Models tested (11):**
- **Anthropic:** Claude Sonnet 4.5, Claude Opus 4.6
- **Google:** Gemini 3 Pro Preview, Gemini 3 Flash Preview, Gemini 2.5 Pro, Gemini 2.5 Flash
- **OpenAI:** GPT-4o, GPT-4o-mini, GPT-5.2
- **Ollama Cloud (open-weight):** DeepSeek V3.2, Qwen3-Coder-Next

**Frameworks:** Python/FastAPI, C#/ASP.NET Core 9, Java/Spring Boot 3  
**Total runs:** 165 entropy-controlled benchmark executions (11 models × 3 tasks × 5 runs)

## Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | ≥ 3.11 | Benchmark runner, FastAPI baseline |
| .NET SDK | 9.0 | ASP.NET Core baseline |
| Java JDK | 17 | Spring Boot baseline |
| Maven | ≥ 3.9 | Spring Boot build |
| Git | any | Cloning this repo |

**API keys** (set the keys for each provider you want to benchmark):
- `OPENAI_API_KEY` — for GPT-4o, GPT-4o-mini, GPT-5.2
- `ANTHROPIC_API_KEY` — for Claude Sonnet 4.5, Claude Opus 4.6
- `GEMINI_API_KEY` (or `GCP_PROJECT_ID` + ADC, or `VERTEX_AI_API_KEY`) — for Gemini 3 Pro/Flash Preview, Gemini 2.5 Pro/Flash
- `OLLAMA_API_KEY` — for DeepSeek V3.2, Qwen3-Coder-Next (via Ollama Cloud)

## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/engramforge/research.git
cd research/llm-codegen-benchmark

# Create Python virtual environment for the benchmark runner
python3 -m venv .venv
source .venv/bin/activate

# Install runner dependencies
pip install -r scripts/requirements.txt
```

### 2. Supply API credentials

```bash
# Set keys for the providers you want to benchmark
export OPENAI_API_KEY="your-openai-key"        # GPT-4o, GPT-4o-mini, GPT-5.2
export ANTHROPIC_API_KEY="your-anthropic-key"    # Claude Sonnet 4.5, Claude Opus 4.6
export GEMINI_API_KEY="your-gemini-key"          # Gemini 3 Pro/Flash, Gemini 2.5 Pro/Flash
export OLLAMA_API_KEY="your-ollama-cloud-key"    # DeepSeek V3.2, Qwen3-Coder-Next
```

### 3. Verify baselines build

Before running benchmarks, confirm the baseline projects compile and pass tests:

```bash
# FastAPI
cd baselines/fastapi
pip install -e ".[dev]"
pytest tests/ -v
mypy app/ --strict
ruff check app/
cd ../..

# ASP.NET Core (requires .NET 9 SDK)
cd baselines/aspnetcore
dotnet build BenchApi.sln
dotnet test tests/BenchApi.Tests/
cd ../..

# Spring Boot (requires JDK 17 + Maven)
cd baselines/springboot
mvn clean test
cd ../..
```

### 4. Run a single benchmark

```bash
source .venv/bin/activate

python scripts/run_benchmark.py \
  --model gpt-4o \
  --task fastapi-001 \
  --entropy-control \
  --min-confidence 0.85 \
  --max-entropy-runs 5
```

### 5. Run the full benchmark suite

```bash
source .venv/bin/activate

# All 11 models from the study:
MODELS=(
  "claude-sonnet-4.5" "claude-opus-4.6"         # Anthropic
  "gemini:gemini-3-pro-preview"                  # Google
  "gemini:gemini-3-flash-preview"
  "gemini:gemini-2.5-pro" "gemini:gemini-2.5-flash"
  "gpt-4o" "gpt-4o-mini" "gpt-5.2"              # OpenAI
  "cloud:deepseek-v3.2" "cloud:qwen3-coder-next" # Ollama Cloud
)
TASKS=("fastapi-001" "aspnetcore-001" "springboot-001")

for model in "${MODELS[@]}"; do
  for task in "${TASKS[@]}"; do
    echo "=== $model on $task ==="
    python scripts/run_benchmark.py \
      --model "$model" \
      --task "$task" \
      --entropy-control \
      --min-confidence 0.85 \
      --max-entropy-runs 5
  done
done
```

### 6. Generate results report

```bash
python scripts/analyze_entropy_results.py
# Output: ENTROPY_RESULTS.md (at repo root)
```

## Repository Structure

```
llm-codegen-benchmark/
├── README.md                       ← you are here
│
├── baselines/                      ← complete, buildable source projects
│   ├── fastapi/                       Python/FastAPI (12 files)
│   │   ├── pyproject.toml                project manifest + dev deps
│   │   ├── app/
│   │   │   ├── __init__.py
│   │   │   ├── main.py                   FastAPI app entrypoint
│   │   │   ├── models/
│   │   │   │   ├── __init__.py
│   │   │   │   └── user.py              Pydantic User models
│   │   │   ├── routers/
│   │   │   │   ├── __init__.py           router registration
│   │   │   │   └── users.py             Users CRUD endpoints
│   │   │   └── dependencies/
│   │   │       ├── __init__.py
│   │   │       └── auth.py              auth dependency injection
│   │   └── tests/
│   │       ├── __init__.py
│   │       ├── conftest.py               test client fixture
│   │       └── test_users.py             Users endpoint tests
│   │
│   ├── aspnetcore/                    C#/ASP.NET Core 9 (9 files)
│   │   ├── BenchApi.sln                  solution file
│   │   ├── src/BenchApi/
│   │   │   ├── BenchApi.csproj           project file
│   │   │   ├── Program.cs               app entrypoint + DI
│   │   │   ├── Controllers/
│   │   │   │   └── UsersController.cs    Users API controller
│   │   │   ├── Models/
│   │   │   │   ├── User.cs              entity model
│   │   │   │   └── UserDto.cs           request/response DTOs
│   │   │   └── Services/
│   │   │       └── UserService.cs        service layer
│   │   └── tests/BenchApi.Tests/
│   │       ├── BenchApi.Tests.csproj     test project
│   │       └── UsersControllerTests.cs   xUnit tests
│   │
│   └── springboot/                    Java/Spring Boot 3 (8 files)
│       ├── pom.xml                       Maven build + deps
│       ├── src/main/java/com/benchmark/
│       │   ├── BenchApplication.java     Spring Boot entrypoint
│       │   ├── controller/
│       │   │   └── UserController.java   REST controller
│       │   ├── model/
│       │   │   ├── User.java            entity model
│       │   │   └── UserDto.java         request/response DTOs
│       │   └── service/
│       │       └── UserService.java      service layer
│       ├── src/main/resources/
│       │   └── application.yml           server config
│       └── src/test/java/com/benchmark/controller/
│           └── UserControllerTest.java   MockMvc tests
│
├── scripts/                        ← benchmark runner + analysis tools
│   ├── requirements.txt               Python deps (openai, anthropic, google-genai, ollama, ...)
│   ├── llm_client.py                  unified LLM client (OpenAI/Anthropic/Gemini/Ollama)
│   ├── run_benchmark.py               main benchmark runner
│   ├── entropy_control.py             variance detection + re-run logic
│   ├── weighted_scoring.py            8-attribute quality scoring
│   ├── static_analysis.py             deterministic code metrics (LOC, complexity, ...)
│   ├── llm_judge.py                   cross-family LLM-as-judge pipeline
│   ├── quality_analysis.py            intra-model consistency + fingerprint extraction
│   ├── adaptive_prompting.py          meta-prompting prompt adaptation
│   ├── compare_preference_impact.py   A/B testing: baseline vs adapted prompts
│   ├── discover_model_preferences.py  meta-prompting preference profiling
│   ├── analyze_metaprompt_results.py  statistical analysis of A/B results
│   ├── analyze_entropy_results.py     results aggregation + report generation
│   ├── aggregate_judge_results.py     collate LLM judge results
│   ├── combined_ranking.py            merged correctness + quality ranking
│   ├── score_all_results.py           batch quality scoring
│   ├── generate_radar.py              fingerprint radar SVG generator
│   ├── isolate_clean_dataset.py       data cleaning (smoke-test/excess removal)
│   ├── regenerate_tables.py           paper-ready markdown table generation
│   ├── run_judge.sh                   shell wrapper for LLM judge
│   └── run_metaprompt_experiment.sh   full meta-prompting experiment pipeline
│
├── prompts/                        ← exact prompt templates used
│   ├── fastapi.txt                    Python/FastAPI prompt
│   ├── aspnetcore.txt                 C#/ASP.NET Core prompt
│   └── springboot.txt                 Java/Spring Boot prompt
│
├── tasks/                          ← task definitions (YAML)
│   ├── fastapi-001.yaml               FastAPI task spec
│   ├── aspnetcore-001.yaml            ASP.NET Core task spec
│   └── springboot-001.yaml            Spring Boot task spec
│
├── model_preferences/              ← meta-prompting preference profiles (11 models)
│   ├── claude-sonnet-4.5.md           Claude Sonnet prompt preferences
│   ├── claude-opus-4.6.md             Claude Opus prompt preferences
│   ├── gpt-4o.md, gpt-4o-mini.md, gpt-5.2.md
│   ├── gemini-gemini-2.5-flash.md ... gemini-gemini-3-pro-preview.md
│   └── cloud-deepseek-v3.2.md, cloud-qwen3-coder-next.md
│
├── data/                           ← our published results (165 runs)
│   ├── entropy_controlled_runs.json   individual run results (48 initial runs)
│   ├── entropy_controlled_runs.csv    same data in CSV
│   ├── summary_statistics.json        aggregated per model×task
│   ├── inter_model_comparison.json    cross-model structural comparison
│   ├── intra_model_consistency.json   within-model variance analysis
│   ├── model_fingerprints.json        per-model behavioral fingerprints
│   └── quality_consistency_frontier.json  quality vs consistency frontier
│
├── pilot/                          ← meta-prompting A/B experiment outputs
│   ├── figures/
│   │   └── llm_judge_quality_scores.svg
│   └── meta_prompting_ab_results.svg
│
├── hooks/                          ← git hooks
│   └── pre-commit-no-secrets          prevents accidental key commits
│
└── diagrams/                       ← architecture & analysis diagrams (12 SVGs)
    ├── benchmark-pipeline.svg         pipeline overview
    ├── entropy-control-flow.svg       entropy control decision flow
    ├── analysis-pipeline.svg          multi-layer analysis pipeline
    ├── analysis-layers.svg            analysis layer breakdown
    ├── code-quality-meta-analysis-framework.svg
    ├── cost-quality-frontier.svg      Pareto frontier visualization
    ├── fingerprint-radar.svg          model behavioral fingerprints
    ├── gate-heatmap.svg               per-model gate pass heatmap
    ├── meta-analysis-pipeline.svg     code quality meta-analysis flow
    ├── quality-consistency-frontier.svg
    ├── statistical-analysis.svg       hypothesis test summary
    └── stylistic-entropy-heatmap.svg  cross-model style variance
```

## How the Benchmark Works

### Quality Gates

Each run scores 0–5 based on sequential quality gates. A gate passes only if all previous gates also passed.

| Gate | FastAPI Tool | ASP.NET Core Tool | Spring Boot Tool |
|------|-------------|-------------------|------------------|
| 1. Diff Extraction | file-block parser | file-block parser | file-block parser |
| 2. Diff Application | file writer | file writer | file writer |
| 3. Tests Pass | `pytest` | `dotnet test` (xUnit) | `mvn test` (Surefire) |
| 4. Type Check | `mypy --strict` | Roslyn compiler | `javac` (Maven) |
| 5. Lint | `ruff check` | Roslyn analyzers | Checkstyle |

### Entropy Control

The entropy controller decides how many runs are needed based on observed variance:

1. Run the benchmark twice (minimum)
2. If standard deviation is zero → stop (high confidence)
3. If variance exceeds threshold → run up to 5 additional times
4. Report mean ± std, confidence interval, and per-gate pass rates

```python
from scripts.entropy_control import EntropyController

controller = EntropyController(min_confidence=0.85, max_runs=5)
results = []

while controller.should_continue(results):
    result = run_benchmark(model, task)
    results.append(result)

stats = controller.get_statistics(results)
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

## Key Findings

| Rank | Model | Mean Gates | σ | Cost/Run | Notes |
|------|-------|-----------|---|----------|-------|
| 1 | Gemini 3 Pro Preview | 5.00 | 0.00 | $0.022 | Only model with perfect 15/15 runs |
| 2 | Claude Sonnet 4.5 | 4.93 | 0.26 | $0.043 | Near-perfect, highest quality prose |
| 3 | Gemini 3 Flash Preview | 4.93 | 0.26 | $0.005 | Best value for near-perfect results |
| 4 | GPT-4o | 4.93 | 0.26 | $0.015 | Good value, variable on ASP.NET |
| 5 | Claude Opus 4.6 | 4.53 | 0.83 | $0.290 | 58× Gemini Flash cost, worse quality |
| 6 | Gemini 2.5 Pro | 4.33 | 0.98 | $0.018 | Mid-tier, unreliable types/tests |
| 7 | Qwen3-Coder-Next | 4.07 | 0.96 | †sub | Open-weight via Ollama Cloud |
| 8 | GPT-5.2 | 4.00 | 1.69 | $0.026 | Bimodal on FastAPI (5/5 or 0/5) |
| 9 | DeepSeek V3.2 | 3.87 | 1.64 | †sub | Open-weight via Ollama Cloud |
| 10 | GPT-4o-mini | 3.60 | 2.13 | $0.001 | Cheapest but unreliable on Python |
| 11 | Gemini 2.5 Flash | 3.33 | 0.62 | $0.007 | Never achieves 5/5 (0% perfect rate) |

*†sub = Ollama Cloud subscription pricing. n=5 per cell, temperature=0.2 across all providers.*

Key observations:
- **Multi-run testing is essential.** Single-run benchmarks produce misleading results — GPT-5.2 on FastAPI scores 5/5 or 0/5 with roughly equal probability.
- **Variance concentrates on Python/FastAPI** while C# and Java tasks are stable across all models.
- **Cost and quality don't always correlate.** Gemini 3 Flash ($0.005/run) outperforms Claude Opus 4.6 ($0.290/run, 58× more expensive).
- **Meta-prompting helps some models but hurts others.** A/B testing (n=5 per condition) showed +6.1% mean improvement but was not significant across all models (sign test p=0.754).

See `data/summary_statistics.json` for full per-task breakdowns.

## Additional Analyses

Beyond the core benchmark, this repository includes:

- **Code quality meta-analysis** — Cross-family LLM-as-judge evaluation of all 165 runs using Gemini 3 Pro Preview and Claude Sonnet 4.5 as judges. Results in `data/model_fingerprints.json`.
- **Meta-prompting experiment** — Preference discovery for all 11 models (profiles in `model_preferences/`) + A/B testing of adapted prompts. Results in `pilot/meta_prompting_ab_results.svg`.
- **Static analysis** — Deterministic metrics (LOC, cyclomatic complexity, nesting depth, type coverage, docstring density) across all 165 runs. Results in `data/intra_model_consistency.json`.

See `LLM_CODEGEN_PILOT_STUDY.md` for the complete write-up.

## Citation

```
EngramForge Engineering. "Measuring LLM Code Generation Consistency
for Platform Integration." February 2026.
https://github.com/engramforge/research/tree/main/llm-codegen-benchmark
```
