# LLM Code Generation Benchmark — Reproduction Package

**Study:** Measuring LLM Code Generation Consistency for Platform Integration  
**Date:** 2026-02-07  
**License:** MIT

---

## Overview

This repository contains everything needed to reproduce our pilot study on LLM code generation quality across enterprise frameworks. It is fully self-contained — no external repositories are required.

The study measured five commercial LLMs against a standardized brownfield task ("add an Orders endpoint") across three frameworks, using entropy-controlled multi-run testing to detect variance that single-run benchmarks miss.

**Models tested:** Claude Sonnet 4.5, GPT-4o, Claude Opus 4.6, GPT-4o-mini, GPT-5.2  
**Frameworks:** Python/FastAPI, C#/ASP.NET Core 9, Java/Spring Boot 3  
**Total runs:** 48 entropy-controlled benchmark executions

## Prerequisites

| Tool | Version | Required For |
|------|---------|-------------|
| Python | ≥ 3.11 | Benchmark runner, FastAPI baseline |
| .NET SDK | 9.0 | ASP.NET Core baseline |
| Java JDK | 17 | Spring Boot baseline |
| Maven | ≥ 3.9 | Spring Boot build |
| Git | any | Cloning this repo |

**API keys** (at least one required):
- `OPENAI_API_KEY` — for GPT-4o, GPT-4o-mini, GPT-5.2
- `ANTHROPIC_API_KEY` — for Claude Sonnet 4.5, Claude Opus 4.6

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
export OPENAI_API_KEY="your-openai-key"
export ANTHROPIC_API_KEY="your-anthropic-key"
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

MODELS=("gpt-4o-mini" "gpt-4o" "claude-sonnet-4.5" "gpt-5.2" "claude-opus-4.6")
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
│   ├── requirements.txt               Python deps (openai, anthropic, pyyaml)
│   ├── run_benchmark.py               main benchmark runner (1300 lines)
│   ├── entropy_control.py             variance detection + re-run logic
│   ├── weighted_scoring.py            8-attribute quality scoring
│   └── analyze_entropy_results.py     results aggregation + report generation
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
├── data/                           ← our published results (48 runs)
│   ├── entropy_controlled_runs.json   individual run results
│   ├── entropy_controlled_runs.csv    same data in CSV
│   └── summary_statistics.json        aggregated per model×task
│
└── diagrams/                       ← architecture diagrams
    ├── benchmark-pipeline.svg         pipeline overview
    └── entropy-control-flow.svg       entropy control decision flow
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

| Model | Mean Gates (All Tasks) | Variance | Cost/Run |
|-------|----------------------|----------|----------|
| Claude Sonnet 4.5 | 5.00 ± 0.00 | None | $0.043 |
| GPT-4o | 4.89 ± 0.33 | Low | $0.016 |
| Claude Opus 4.6 | 4.67 ± 0.47 | Low | $0.282 |
| GPT-4o-mini | 4.33 ± 1.25 | **High on Python** | $0.001 |
| GPT-5.2 | 4.00 ± 1.63 | **High on Python** | $0.026 |

The most notable finding: variance concentrates on Python/FastAPI while C# and Java tasks are stable across all models. See `data/summary_statistics.json` for full per-task breakdowns.

## Citation

```
EngramForge Engineering. "Measuring LLM Code Generation Consistency
for Platform Integration." February 2026.
https://github.com/engramforge/research/tree/main/llm-codegen-benchmark
```
