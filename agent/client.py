"""Nebius Token Factory client (OpenAI-compatible).

Reads credentials from the environment:
    NEBIUS_API_KEY  - API key from https://tokenfactory.nebius.com (API Keys page)
Optional overrides:
    NEBIUS_BASE_URL - default https://api.tokenfactory.nebius.com/v1/
    NEBIUS_MODEL    - default nvidia/nemotron-3-super-120b-a12b
"""

from __future__ import annotations

import json
import os

DEFAULT_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
DEFAULT_MODEL = "nvidia/nemotron-3-super-120b-a12b"


class NebiusConfigError(RuntimeError):
    """Raised when the Nebius API key is missing."""


def build_client(api_key: str | None = None, base_url: str | None = None):
    """Create an OpenAI-compatible client pointed at Nebius Token Factory."""
    key = api_key or os.environ.get("NEBIUS_API_KEY")
    if not key:
        raise NebiusConfigError(
            "NEBIUS_API_KEY is not set. Sign up free at https://tokenfactory.nebius.com, "
            "create an API key (API Keys -> Create New Key), and export it as "
            "NEBIUS_API_KEY before running Clausewise."
        )
    from openai import OpenAI  # imported lazily so tests don't need the package

    return OpenAI(
        api_key=key,
        base_url=base_url or os.environ.get("NEBIUS_BASE_URL", DEFAULT_BASE_URL),
    )


def model_id() -> str:
    return os.environ.get("NEBIUS_MODEL", DEFAULT_MODEL)


def _strip_code_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first fence line and trailing fence
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def complete_json(
    client,
    system: str,
    user: str,
    *,
    model: str | None = None,
    temperature: float = 0.2,
    max_tokens: int = 4000,
) -> dict | list:
    """One chat-completion call, returning parsed JSON.

    Uses response_format json_object when supported and falls back to
    plain parsing (with fence-stripping) otherwise.
    """
    kwargs: dict = {
        "model": model or model_id(),
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    try:
        response = client.chat.completions.create(
            **kwargs, response_format={"type": "json_object"}
        )
    except Exception:
        # Endpoint/SDK combination that rejects response_format — retry plain.
        response = client.chat.completions.create(**kwargs)
    content = response.choices[0].message.content or ""
    return json.loads(_strip_code_fences(content))
