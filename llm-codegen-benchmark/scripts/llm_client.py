#!/usr/bin/env python3
"""Unified LLM client interface for all supported backends.

Provides a single `call_llm(model, prompt, ...)` entry point that routes
to the appropriate backend based on model name prefix/lookup.

Supported backends:
  - OpenAI API      (GPT-4o, GPT-4o-mini, GPT-5.2, o1, o3)
  - Anthropic API   (Claude Opus, Claude Sonnet, Claude Haiku)
  - Google Gemini   (Vertex AI → AI Studio → Express fallback)
  - Ollama Cloud    (DeepSeek, Qwen via ollama.com API)
  - Ollama Local    (any model via local daemon)

Usage:
    from llm_client import call_llm, determine_backend

    text, usage = call_llm("gpt-4o", "Hello world", max_tokens=1024)
    text, usage = call_llm("claude-sonnet-4.5", "Hello", temperature=0.5)
    text, usage = call_llm("gemini:gemini-2.5-pro", "Hi")
    text, usage = call_llm("cloud:deepseek-v3.2", "Hi")

The `usage` dict always contains these normalized keys:
    input_tokens:  int
    output_tokens: int
    total_tokens:  int
    estimated_cost_usd: float
    api_response_time_seconds: float
    stop_reason: str | None   ("stop", "max_tokens", "length", etc.)
    truncated: bool
"""

from __future__ import annotations

import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from typing import Optional

# ── Optional SDK imports ────────────────────────────────────────────
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False

try:
    from ollama import Client as OllamaClient
    OLLAMA_SDK_AVAILABLE = True
except ImportError:
    OLLAMA_SDK_AVAILABLE = False

try:
    from google import genai
    from google.genai import types as genai_types
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ── Model registries ───────────────────────────────────────────────

OPENAI_MODELS = {
    "gpt-5.2": "gpt-5.2",
    "gpt-5.2-pro": "gpt-5.2-pro",
    "gpt-5.2-chat-latest": "gpt-5.2-chat-latest",
    "gpt-4o": "gpt-4o",
    "gpt-4o-mini": "gpt-4o-mini",
    "gpt-4-turbo": "gpt-4-turbo",
    "o1": "o1",
    "o1-mini": "o1-mini",
    "o3-mini": "o3-mini",
}

OPENAI_PRICING: dict[str, tuple[float, float]] = {
    "gpt-5.2": (5.00, 15.00),
    "gpt-5.2-pro": (10.00, 30.00),
    "gpt-5.2-chat-latest": (5.00, 15.00),
    "gpt-5.2-codex": (7.50, 22.50),
    "gpt-4o": (2.50, 10.00),
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4-turbo": (10.00, 30.00),
    "o1": (15.00, 60.00),
    "o1-mini": (3.00, 12.00),
    "o3-mini": (3.00, 12.00),
}

ANTHROPIC_MODELS = {
    "claude-opus-4.6": "claude-opus-4-6",
    "claude-opus-4-6": "claude-opus-4-6",
    "claude-sonnet-4.5": "claude-sonnet-4-5-20250929",
    "claude-haiku-4.5": "claude-haiku-4-5-20251001",
    "claude-opus-4.5": "claude-opus-4-5-20251101",
    "claude-opus": "claude-opus-4-20250514",
    "claude-sonnet": "claude-sonnet-4-20250514",
    "claude-4-opus": "claude-4-opus-20250514",
    "claude-4-sonnet": "claude-4-sonnet-20250514",
    "claude-sonnet-4-5-20250929": "claude-sonnet-4-5-20250929",
    "claude-haiku-4-5-20251001": "claude-haiku-4-5-20251001",
    "claude-opus-4-5-20251101": "claude-opus-4-5-20251101",
    "claude-opus-4-20250514": "claude-opus-4-20250514",
    "claude-sonnet-4-20250514": "claude-sonnet-4-20250514",
    "claude-4-opus-20250514": "claude-4-opus-20250514",
    "claude-4-sonnet-20250514": "claude-4-sonnet-20250514",
    "claude-3-opus": "claude-3-opus-20240229",
    "claude-3-sonnet": "claude-3-5-sonnet-20241022",
}

ANTHROPIC_PRICING: dict[str, tuple[float, float]] = {
    "claude-opus-4-6": (25.00, 125.00),
    "claude-sonnet-4-5-20250929": (3.50, 17.50),
    "claude-haiku-4-5-20251001": (0.80, 4.00),
    "claude-opus-4-5-20251101": (20.00, 100.00),
    "claude-opus-4-20250514": (15.00, 75.00),
    "claude-sonnet-4-20250514": (3.00, 15.00),
    "claude-4-opus-20250514": (15.00, 75.00),
    "claude-4-sonnet-20250514": (3.00, 15.00),
    "claude-3-opus-20240229": (15.00, 75.00),
    "claude-3-5-sonnet-20241022": (3.00, 15.00),
}

GEMINI_MODELS = {
    "gemini-3-flash-preview": "gemini-3-flash-preview",
    "gemini-3-pro-preview": "gemini-3-pro-preview",
    "gemini-2.5-flash": "gemini-2.5-flash",
    "gemini-2.5-pro": "gemini-2.5-pro",
}

GEMINI_PRICING: dict[str, tuple[float, float]] = {
    "gemini-3-flash-preview": (0.50, 3.00),
    "gemini-3-pro-preview": (2.00, 12.00),
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.5-pro": (1.25, 10.00),
}

OLLAMA_CLOUD_PRICING: dict[str, tuple[float, float]] = {
    "qwen3-coder-next": (2.00, 6.00),
    "deepseek-v3.2": (2.00, 6.00),
}


# ── Backend detection ──────────────────────────────────────────────

def determine_backend(model: str) -> str:
    """Determine which backend to use for a model.

    Returns one of: "openai", "anthropic", "gemini", "ollama_cloud", "ollama".
    """
    if model.startswith("gemini:"):
        return "gemini"
    if model.startswith("cloud:"):
        return "ollama_cloud"
    if model.startswith("ollama:"):
        return "ollama"
    if model in OPENAI_MODELS or model.startswith(("gpt-", "o1", "o3")):
        return "openai"
    if model in ANTHROPIC_MODELS or model.startswith("claude"):
        return "anthropic"
    if model in GEMINI_MODELS or model.startswith("gemini-"):
        return "gemini"
    return "ollama"


# ── Normalized usage dict builder ──────────────────────────────────

def _make_usage(
    input_tokens: int = 0,
    output_tokens: int = 0,
    estimated_cost_usd: float = 0.0,
    api_response_time_seconds: float = 0.0,
    stop_reason: Optional[str] = None,
    truncated: bool = False,
    **extra,
) -> dict:
    """Build a normalized usage dict with consistent keys across all backends."""
    usage = {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": input_tokens + output_tokens,
        "estimated_cost_usd": estimated_cost_usd,
        "api_response_time_seconds": api_response_time_seconds,
        "stop_reason": stop_reason,
        "truncated": truncated,
    }
    usage.update(extra)
    return usage


def _estimate_cost(
    input_tokens: int, output_tokens: int, pricing: tuple[float, float]
) -> float:
    return (input_tokens * pricing[0] / 1_000_000) + (
        output_tokens * pricing[1] / 1_000_000
    )


# ── Per-backend call implementations ──────────────────────────────

def _call_openai(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    verbose: bool,
) -> tuple[str, dict]:
    if not OPENAI_AVAILABLE:
        raise ImportError("openai package not installed. Run: pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set")

    client = openai.OpenAI(api_key=api_key)
    model_id = OPENAI_MODELS.get(model, model)

    if verbose:
        print(f"Calling OpenAI API with model: {model_id} (max_tokens: {max_tokens})")

    # GPT-5.x uses max_completion_tokens
    token_param = "max_completion_tokens" if "gpt-5" in model_id else "max_tokens"

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    start = time.time()
    response = client.chat.completions.create(
        model=model_id,
        messages=messages,
        **{token_param: max_tokens},
        temperature=temperature,
    )
    elapsed = time.time() - start

    finish = response.choices[0].finish_reason
    truncated = finish == "length"
    in_tok = response.usage.prompt_tokens
    out_tok = response.usage.completion_tokens
    pricing = OPENAI_PRICING.get(model_id, (0, 0))

    usage = _make_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=_estimate_cost(in_tok, out_tok, pricing),
        api_response_time_seconds=elapsed,
        stop_reason=finish,
        truncated=truncated,
    )

    if verbose:
        print(f"  API response time: {elapsed:.2f}s")
        print(f"  Tokens: {in_tok} in, {out_tok} out")
        print(f"  Finish: {finish}")
        if truncated:
            print("  ⚠️  TRUNCATED - hit max_tokens limit!")
        print(f"  Cost: ${usage['estimated_cost_usd']:.4f}")

    return response.choices[0].message.content, usage


def _call_anthropic(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    verbose: bool,
) -> tuple[str, dict]:
    if not ANTHROPIC_AVAILABLE:
        raise ImportError("anthropic package not installed. Run: pip install anthropic")

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY environment variable not set")

    client = anthropic.Anthropic(api_key=api_key)
    model_id = ANTHROPIC_MODELS.get(model, model)

    if verbose:
        print(f"Calling Anthropic API with model: {model_id} (max_tokens: {max_tokens})")

    kwargs = {}
    if system_prompt:
        kwargs["system"] = system_prompt

    start = time.time()
    response = client.messages.create(
        model=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
        **kwargs,
    )
    elapsed = time.time() - start

    stop = response.stop_reason
    truncated = stop == "max_tokens"
    in_tok = response.usage.input_tokens
    out_tok = response.usage.output_tokens
    pricing = ANTHROPIC_PRICING.get(model_id, (0, 0))

    usage = _make_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=_estimate_cost(in_tok, out_tok, pricing),
        api_response_time_seconds=elapsed,
        stop_reason=stop,
        truncated=truncated,
    )

    if verbose:
        print(f"  API response time: {elapsed:.2f}s")
        print(f"  Tokens: {in_tok} in, {out_tok} out")
        print(f"  Stop: {stop}")
        if truncated:
            print("  ⚠️  TRUNCATED - hit max_tokens limit!")
        print(f"  Cost: ${usage['estimated_cost_usd']:.4f}")

    return response.content[0].text, usage


def _call_ollama(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    verbose: bool,
) -> tuple[str, dict]:
    """Call local Ollama daemon via the SDK (with subprocess fallback)."""
    model_name = model.removeprefix("ollama:")

    if verbose:
        print(f"Calling Ollama (local) with model: {model_name}")

    start = time.time()

    if OLLAMA_SDK_AVAILABLE:
        # Prefer the SDK — gets token counts and respects temperature
        client = OllamaClient()
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat(
            model=model_name,
            messages=messages,
            stream=False,
            options={
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        )
        elapsed = time.time() - start
        output = response.message.content or ""
        in_tok = getattr(response, "prompt_eval_count", 0) or 0
        out_tok = getattr(response, "eval_count", 0) or 0
        done_reason = getattr(response, "done_reason", None)
    else:
        # Fallback: subprocess (no token counts, no temperature control)
        result = subprocess.run(
            ["ollama", "run", model_name, "--nowordwrap"],
            input=prompt,
            capture_output=True,
            text=True,
            timeout=600,
        )
        elapsed = time.time() - start
        output = re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', result.stdout)
        in_tok, out_tok, done_reason = 0, 0, None

    usage = _make_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=0.0,
        api_response_time_seconds=elapsed,
        stop_reason=done_reason,
        truncated=False,
    )

    if verbose:
        print(f"  Local model (no cost), {elapsed:.1f}s")
        if in_tok:
            print(f"  Tokens: {in_tok} in, {out_tok} out")

    return output, usage


def _call_ollama_cloud(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    verbose: bool,
) -> tuple[str, dict]:
    if not OLLAMA_SDK_AVAILABLE:
        raise ImportError("ollama package not installed. Run: pip install ollama")

    api_key = os.environ.get("OLLAMA_API_KEY")
    if not api_key:
        raise ValueError("OLLAMA_API_KEY environment variable not set")

    model_name = model.removeprefix("cloud:")

    client = OllamaClient(
        host="https://ollama.com",
        headers={"Authorization": f"Bearer {api_key}"},
    )

    if verbose:
        print(f"Calling Ollama Cloud with model: {model_name} (temp: {temperature}, max_tokens: {max_tokens})")

    start = time.time()

    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    # Retry on transient 500 errors
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat(
                model=model_name,
                messages=messages,
                stream=False,
                options={
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            )
            break
        except Exception as e:
            if attempt < max_retries and "500" in str(e):
                wait = attempt * 10
                if verbose:
                    print(f"  ⚠️  Attempt {attempt}/{max_retries} failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    elapsed = time.time() - start
    output = response.message.content or ""
    in_tok = getattr(response, "prompt_eval_count", 0) or 0
    out_tok = getattr(response, "eval_count", 0) or 0
    done_reason = getattr(response, "done_reason", None)

    pricing = OLLAMA_CLOUD_PRICING.get(model_name, (2.00, 6.00))

    usage = _make_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=_estimate_cost(in_tok, out_tok, pricing),
        api_response_time_seconds=elapsed,
        stop_reason=done_reason,
        truncated=False,
        cost_note="amortized from Ollama Cloud subscription (not per-token)",
    )

    if verbose:
        print(f"  API response time: {elapsed:.2f}s")
        print(f"  Tokens: {in_tok} in, {out_tok} out")
        if done_reason:
            print(f"  Done reason: {done_reason}")

    return output, usage


def _call_gemini(
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    system_prompt: Optional[str],
    verbose: bool,
) -> tuple[str, dict]:
    if not GEMINI_AVAILABLE:
        raise ImportError("google-genai package not installed. Run: pip install google-genai")

    model_name = model.removeprefix("gemini:")

    # ── Auth: try full Vertex AI → AI Studio key → Express key ──
    gcp_project = os.environ.get("GCP_PROJECT_ID") or os.environ.get("VERTEX_AI_PROJECT")
    vertex_location = os.environ.get("VERTEX_AI_LOCATION", "us-central1")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    vertex_key = os.environ.get("VERTEX_AI_API_KEY")

    if "gemini-3" in model_name:
        vertex_location = "global"

    auth_attempts = []
    if gcp_project:
        auth_attempts.append(("vertexai", lambda: genai.Client(
            vertexai=True, project=gcp_project, location=vertex_location,
        ), f"Vertex AI (project={gcp_project}, location={vertex_location})"))
    if gemini_key:
        auth_attempts.append(("aistudio", lambda: genai.Client(api_key=gemini_key), "AI Studio"))
    if vertex_key:
        auth_attempts.append(("vertexai_express", lambda: genai.Client(
            vertexai=True, api_key=vertex_key,
        ), "Vertex AI Express"))

    if not auth_attempts:
        raise ValueError(
            "Gemini auth not configured. Set one of:\n"
            "  1. GCP_PROJECT_ID + gcloud auth application-default login\n"
            "  2. GEMINI_API_KEY (from https://aistudio.google.com/app/apikey)\n"
            "  3. VERTEX_AI_API_KEY (Vertex AI Express)"
        )

    # Try each auth mode, fall back on auth errors
    client = None
    for _mode, client_factory, label in auth_attempts:
        try:
            client = client_factory()
            if verbose:
                print(f"Calling Gemini ({label}) with model: {model_name}")
            break
        except Exception as e:
            err = str(e).lower()
            if any(k in err for k in ("reauthentication", "credentials", "auth")):
                if verbose:
                    print(f"  ⚠️  {label} auth failed, trying next method...")
                client = None
                continue
            raise

    if client is None:
        raise ValueError("All Gemini auth methods failed.")

    if verbose:
        print(f"  temp: {temperature}, max_tokens: {max_tokens}")

    # Build contents — Gemini supports system_instruction natively
    config_kwargs: dict = {
        "temperature": temperature,
        "max_output_tokens": max_tokens,
    }
    gen_kwargs: dict = {
        "model": model_name,
        "contents": prompt,
        "config": genai_types.GenerateContentConfig(**config_kwargs),
    }
    if system_prompt:
        gen_kwargs["config"] = genai_types.GenerateContentConfig(
            **config_kwargs,
            system_instruction=system_prompt,
        )

    start = time.time()

    # Retry on transient errors; fall back auth on credential errors
    max_retries = 3
    auth_fallback_done = False
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(**gen_kwargs)
            break
        except Exception as e:
            err = str(e).lower()
            if not auth_fallback_done and any(
                k in err for k in ("reauthentication", "credentials", "refresh")
            ):
                auth_fallback_done = True
                for _m, cf, lbl in auth_attempts[1:]:
                    try:
                        client = cf()
                        if verbose:
                            print(f"  ⚠️  ADC expired, falling back to {lbl}")
                        break
                    except Exception:
                        continue
                else:
                    raise
                continue
            elif attempt < max_retries and any(c in str(e) for c in ("500", "503", "429")):
                wait = attempt * 10
                if verbose:
                    print(f"  ⚠️  Attempt {attempt}/{max_retries} failed ({e}), retrying in {wait}s...")
                time.sleep(wait)
            else:
                raise

    elapsed = time.time() - start
    output = response.text or ""

    meta = response.usage_metadata
    in_tok = getattr(meta, "prompt_token_count", 0) or 0
    out_tok = getattr(meta, "candidates_token_count", 0) or 0
    pricing = GEMINI_PRICING.get(model_name, (0, 0))

    finish = None
    if response.candidates:
        finish = str(response.candidates[0].finish_reason)
    truncated = bool(finish and "MAX_TOKENS" in str(finish))

    usage = _make_usage(
        input_tokens=in_tok,
        output_tokens=out_tok,
        estimated_cost_usd=_estimate_cost(in_tok, out_tok, pricing),
        api_response_time_seconds=elapsed,
        stop_reason=finish,
        truncated=truncated,
    )

    if verbose:
        print(f"  Tokens: {in_tok} in, {out_tok} out")
        print(f"  API response time: {elapsed:.2f}s")
        print(f"  Finish: {finish}")
        if truncated:
            print("  ⚠️  TRUNCATED - hit max_tokens limit!")
        print(f"  Cost: ${usage['estimated_cost_usd']:.4f}")

    return output, usage


# ── Public API ─────────────────────────────────────────────────────

# Dispatch table — maps backend name to implementation
_BACKENDS = {
    "openai": _call_openai,
    "anthropic": _call_anthropic,
    "gemini": _call_gemini,
    "ollama_cloud": _call_ollama_cloud,
    "ollama": _call_ollama,
}


def call_llm(
    model: str,
    prompt: str,
    *,
    max_tokens: int = 8192,
    temperature: float = 0.2,
    system_prompt: Optional[str] = None,
    verbose: bool = True,
) -> tuple[str, dict]:
    """Call any supported LLM and return (text, normalized_usage).

    Args:
        model: Model identifier with optional prefix
               ("gpt-4o", "claude-sonnet-4.5", "gemini:gemini-2.5-pro",
                "cloud:deepseek-v3.2", "ollama:llama3")
        prompt: User prompt text
        max_tokens: Maximum output tokens (default 8192)
        temperature: Sampling temperature (default 0.2)
        system_prompt: Optional system message (supported by all backends)
        verbose: Print progress/cost info (default True)

    Returns:
        (output_text, usage_dict) where usage_dict always contains:
            input_tokens, output_tokens, total_tokens,
            estimated_cost_usd, api_response_time_seconds,
            stop_reason, truncated
    """
    backend = determine_backend(model)
    fn = _BACKENDS.get(backend)
    if fn is None:
        raise ValueError(f"Unknown backend: {backend!r} for model {model!r}")

    if verbose:
        print(f"Using backend: {backend}")

    return fn(
        model=model,
        prompt=prompt,
        max_tokens=max_tokens,
        temperature=temperature,
        system_prompt=system_prompt,
        verbose=verbose,
    )


# ── Convenience re-exports for backward compatibility ──────────────
# These allow: from llm_client import call_openai, call_anthropic, ...

def call_openai(model: str, prompt: str, max_tokens: int = 8192, temperature: float = 0.2) -> tuple[str, dict]:
    """Backward-compatible wrapper for OpenAI calls."""
    return _call_openai(model, prompt, max_tokens, temperature, system_prompt=None, verbose=True)

def call_anthropic(model: str, prompt: str, max_tokens: int = 8192, temperature: float = 0.2) -> tuple[str, dict]:
    """Backward-compatible wrapper for Anthropic calls."""
    return _call_anthropic(model, prompt, max_tokens, temperature, system_prompt=None, verbose=True)

def call_gemini(model: str, prompt: str, max_tokens: int = 8192, temperature: float = 0.2) -> tuple[str, dict]:
    """Backward-compatible wrapper for Gemini calls."""
    return _call_gemini(model, prompt, max_tokens, temperature, system_prompt=None, verbose=True)

def call_ollama(model: str, prompt: str, temperature: float = 0.2) -> tuple[str, dict]:
    """Backward-compatible wrapper for local Ollama calls."""
    return _call_ollama(model, prompt, 8192, temperature, system_prompt=None, verbose=True)

def call_ollama_cloud(model: str, prompt: str, temperature: float = 0.2, max_tokens: int = 8192) -> tuple[str, dict]:
    """Backward-compatible wrapper for Ollama Cloud calls (note: param order preserved)."""
    return _call_ollama_cloud(model, prompt, max_tokens, temperature, system_prompt=None, verbose=True)
