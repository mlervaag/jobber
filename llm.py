"""
Shared LLM helpers for the scoring scripts (score.py, score_agents.py,
score_industries.py, qa_agents.py).

Models starting with "claude-" use the Anthropic Messages API; all others use
the OpenAI Chat Completions API. API keys are read from .env / .env.local.
"""

import json
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv(".env")
load_dotenv(".env.local", override=True)

RETRY_STATUS = {429, 500, 502, 503, 504, 529}


def is_anthropic_model(model):
    """Check if the model string refers to an Anthropic/Claude model."""
    return model.startswith("claude-")


def require_api_key(model):
    """Return an error message if the API key for `model` is missing, else None."""
    key = "ANTHROPIC_API_KEY" if is_anthropic_model(model) else "OPENAI_API_KEY"
    if not os.environ.get(key):
        return f"Error: {key} not set in .env or .env.local"
    return None


def parse_json_response(content):
    """Strip markdown code fences if present and parse JSON."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        if content.rstrip().endswith("```"):
            content = content.rstrip()[:-3]
        content = content.strip()
    return json.loads(content)


def _post(client, url, headers, payload, timeout, retries):
    """POST with exponential backoff on rate limits, server errors and timeouts."""
    for attempt in range(retries + 1):
        try:
            response = client.post(url, headers=headers, json=payload, timeout=timeout)
            if response.status_code in RETRY_STATUS and attempt < retries:
                wait = float(response.headers.get("retry-after", 0) or 0) or 2 ** (attempt + 1)
                print(f"(HTTP {response.status_code}, retrying in {wait:.0f}s)", end=" ", flush=True)
                time.sleep(wait)
                continue
            response.raise_for_status()
            return response.json()
        except (httpx.TimeoutException, httpx.TransportError):
            if attempt >= retries:
                raise
            time.sleep(2 ** (attempt + 1))
    raise RuntimeError("unreachable")


def complete(client, system, user, model, max_tokens=400, temperature=0.2,
             timeout=60, retries=3):
    """Send one system+user prompt to the model and return the text reply."""
    if is_anthropic_model(model):
        data = _post(
            client,
            "https://api.anthropic.com/v1/messages",
            {
                "x-api-key": os.environ["ANTHROPIC_API_KEY"],
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            {
                "model": model,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "system": system,
                "messages": [{"role": "user", "content": user}],
            },
            timeout, retries,
        )
        return "".join(b.get("text", "") for b in data["content"] if b.get("type") == "text")

    data = _post(
        client,
        "https://api.openai.com/v1/chat/completions",
        {"Authorization": f"Bearer {os.environ['OPENAI_API_KEY']}"},
        {
            "model": model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": temperature,
        },
        timeout, retries,
    )
    return data["choices"][0]["message"]["content"]


def complete_json(client, system, user, model, **kwargs):
    """Like complete(), but parse the reply as JSON."""
    return parse_json_response(complete(client, system, user, model, **kwargs))


def validate_score(result, key):
    """Validate an LLM score reply: `key` must be 0-10, rationale a non-empty string.

    Returns a cleaned dict {key: int, "rationale": str} or raises ValueError.
    """
    if not isinstance(result, dict):
        raise ValueError(f"expected JSON object, got {type(result).__name__}")
    raw = result.get(key)
    try:
        value = float(raw)
    except (TypeError, ValueError):
        raise ValueError(f"{key} is not a number: {raw!r}")
    if not 0 <= value <= 10:
        raise ValueError(f"{key} out of range 0-10: {raw!r}")
    rationale = result.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise ValueError("missing rationale")
    return {key: int(round(value)), "rationale": rationale.strip()}
