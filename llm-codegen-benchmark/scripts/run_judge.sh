#!/bin/bash
# Run the LLM judge pipeline with env vars exported
set -a
source /Users/jgray/projects/ai/llm-codebench/.env.local
set +a
export PYTHONUNBUFFERED=1
exec /Users/jgray/projects/ai/llm-codebench/pilot/.venv/bin/python \
    /Users/jgray/projects/ai/llm-codebench/pilot/llm_judge.py "$@"
