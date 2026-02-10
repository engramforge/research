#!/usr/bin/env bash
# =============================================================================
# Meta-Prompting Experiment: Profile all 11 models + A/B test on FastAPI
#
# Phase 1: Discover preferences for the 9 models not yet profiled
# Phase 2: A/B test all 11 models on fastapi-001 (n=5 per condition)
#
# Existing profiles: claude-sonnet-4.5, gpt-4o-mini
# Existing baseline: 5 entropy-controlled runs per model on fastapi-001
#
# Usage:
#   ./pilot/run_metaprompt_experiment.sh              # Full run
#   ./pilot/run_metaprompt_experiment.sh --profile-only  # Phase 1 only
#   ./pilot/run_metaprompt_experiment.sh --ab-only       # Phase 2 only (needs profiles)
#   ./pilot/run_metaprompt_experiment.sh --dry-run       # Show plan without running
# =============================================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

# Use the venv Python (has all SDKs: anthropic, openai, ollama, google-genai)
PYTHON="${SCRIPT_DIR}/.venv/bin/python"

# Load API keys from .env.local if present
if [[ -f .env.local ]]; then
    echo "Loading API keys from .env.local..."
    set -a
    source .env.local
    set +a
elif [[ -f .env ]]; then
    echo "Loading API keys from .env..."
    set -a
    source .env
    set +a
fi

# All 11 models in the clean dataset
ALL_MODELS=(
    "claude-opus-4.6"
    "claude-sonnet-4.5"
    "cloud:deepseek-v3.2"
    "cloud:qwen3-coder-next"
    "gemini:gemini-2.5-flash"
    "gemini:gemini-2.5-pro"
    "gemini:gemini-3-flash-preview"
    "gemini:gemini-3-pro-preview"
    "gpt-4o"
    "gpt-4o-mini"
    "gpt-5.2"
)

# Models already profiled
ALREADY_PROFILED=("claude-sonnet-4.5" "gpt-4o-mini")

# Task for A/B testing (highest variance = most room for improvement)
AB_TASK="fastapi-001"
RUNS_PER_CONDITION=5

# Parse arguments
DRY_RUN=false
PROFILE_ONLY=false
AB_ONLY=false
for arg in "$@"; do
    case $arg in
        --dry-run) DRY_RUN=true ;;
        --profile-only) PROFILE_ONLY=true ;;
        --ab-only) AB_ONLY=true ;;
        *) echo "Unknown argument: $arg"; exit 1 ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 1: Discover preferences for unprofiled models
# ─────────────────────────────────────────────────────────────────────────────
run_phase1() {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "PHASE 1: Discover Model Preferences"
    echo "═══════════════════════════════════════════════════════════════════"

    local profiled=0
    local skipped=0
    local failed=0

    for model in "${ALL_MODELS[@]}"; do
        # Check if already profiled
        local safe_name
        safe_name="$(echo "$model" | tr ':/' '-')"
        local profile_file="pilot/model_preferences/${safe_name}.md"

        if [[ -f "$profile_file" ]]; then
            echo "  ✓ $model — already profiled ($profile_file)"
            ((skipped++))
            continue
        fi

        echo ""
        echo "  → Profiling: $model"

        if $DRY_RUN; then
            echo "    [DRY RUN] python pilot/discover_model_preferences.py --model '$model'"
            ((profiled++))
            continue
        fi

        if "$PYTHON" pilot/discover_model_preferences.py --model "$model" 2>&1; then
            echo "  ✓ $model profiled successfully"
            ((profiled++))
        else
            echo "  ✗ $model FAILED"
            ((failed++))
        fi

        # Brief pause between API calls
        sleep 2
    done

    echo ""
    echo "Phase 1 complete: $profiled new profiles, $skipped already existed, $failed failed"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# PHASE 2: A/B test all models on FastAPI
# ─────────────────────────────────────────────────────────────────────────────
run_phase2() {
    echo "═══════════════════════════════════════════════════════════════════"
    echo "PHASE 2: A/B Testing (Baseline vs Preference-Adapted)"
    echo "  Task: $AB_TASK"
    echo "  Runs per condition: $RUNS_PER_CONDITION"
    echo "  Note: Baseline runs already exist (n=5 per model from entropy grid)"
    echo "  Only running ADAPTED condition (with preferences)"
    echo "═══════════════════════════════════════════════════════════════════"

    local completed=0
    local failed=0

    for model in "${ALL_MODELS[@]}"; do
        # Check profile exists
        local safe_name
        safe_name="$(echo "$model" | tr ':/' '-')"
        local profile_file="pilot/model_preferences/${safe_name}.md"

        if [[ ! -f "$profile_file" ]]; then
            echo "  ⚠ $model — no preference profile found, skipping A/B test"
            ((failed++))
            continue
        fi

        echo ""
        echo "  → A/B testing: $model on $AB_TASK (${RUNS_PER_CONDITION} adapted runs)"

        if $DRY_RUN; then
            echo "    [DRY RUN] python pilot/compare_preference_impact.py --model '$model' --task '$AB_TASK' --runs $RUNS_PER_CONDITION"
            ((completed++))
            continue
        fi

        if "$PYTHON" pilot/compare_preference_impact.py \
            --model "$model" \
            --task "$AB_TASK" \
            --runs "$RUNS_PER_CONDITION" 2>&1; then
            echo "  ✓ $model A/B test complete"
            ((completed++))
        else
            echo "  ✗ $model A/B test FAILED"
            ((failed++))
        fi

        # Pause between models to avoid rate limits
        sleep 5
    done

    echo ""
    echo "Phase 2 complete: $completed models tested, $failed failed/skipped"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Summary
# ─────────────────────────────────────────────────────────────────────────────
print_plan() {
    echo ""
    echo "╔═══════════════════════════════════════════════════════════════════╗"
    echo "║           META-PROMPTING EXPERIMENT PLAN                        ║"
    echo "╠═══════════════════════════════════════════════════════════════════╣"
    echo "║ Phase 1: Profile 9 remaining models (~30s each, ~\$2-5 total)    ║"
    echo "║ Phase 2: A/B test 11 models × 5 adapted runs (~\$8-15 total)    ║"
    echo "║                                                                 ║"
    echo "║ Baseline data: existing 5 entropy-controlled runs per model     ║"
    echo "║ New runs: 55 adapted runs (11 models × 5 runs × 1 task)         ║"
    echo "║ Total new API calls: ~64 (9 profiles + 55 adapted benchmark)    ║"
    echo "║ Estimated cost: \$10-20                                          ║"
    echo "║ Estimated time: ~45-60 minutes                                  ║"
    echo "╚═══════════════════════════════════════════════════════════════════╝"
    echo ""
}

# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────
print_plan

if $DRY_RUN; then
    echo "[DRY RUN MODE — no API calls will be made]"
    echo ""
fi

if ! $AB_ONLY; then
    run_phase1
fi

if ! $PROFILE_ONLY; then
    run_phase2
fi

echo "═══════════════════════════════════════════════════════════════════"
echo "EXPERIMENT COMPLETE"
echo ""
echo "Next steps:"
echo "  1. Review profiles:  ls pilot/model_preferences/"
echo "  2. Review A/B data:  ls pilot/preference_comparisons/"
echo "  3. Analyze results:  python pilot/analyze_metaprompt_results.py"
echo "  4. Update paper §4.3, §4.4, §5.4 with expanded results"
echo "═══════════════════════════════════════════════════════════════════"
