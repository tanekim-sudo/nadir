"""Thin wrapper around Anthropic client with model routing."""
import json
import logging
from typing import Any, Dict

import anthropic

from app.core.config import get_settings

logger = logging.getLogger(__name__)


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=get_settings().anthropic_api_key)


def call_haiku(prompt: str, system: str = "", max_tokens: int = 4096) -> str:
    """High-volume extraction tasks (GRR, moral language, signal scoring)."""
    settings = get_settings()
    messages = [{"role": "user", "content": prompt}]
    kwargs: Dict[str, Any] = dict(
        model=settings.anthropic_model_haiku,
        max_tokens=max_tokens,
        messages=messages,
    )
    if system:
        kwargs["system"] = system
    resp = _client().messages.create(**kwargs)
    return resp.content[0].text


def call_opus(prompt: str, system: str = "", max_tokens: int = 8192) -> str:
    """Low-volume, high-quality tasks (belief stacks, thesis generation)."""
    settings = get_settings()
    messages = [{"role": "user", "content": prompt}]
    kwargs: Dict[str, Any] = dict(
        model=settings.anthropic_model_opus,
        max_tokens=max_tokens,
        messages=messages,
    )
    if system:
        kwargs["system"] = system
    resp = _client().messages.create(**kwargs)
    return resp.content[0].text


def parse_json_response(text: str) -> Dict[str, Any]:
    """Extract JSON from Claude response, handling markdown fences."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.split("\n")
        lines = lines[1:]  # drop opening fence
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)
    cleaned = cleaned.replace("'", '"')
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        logger.error("Failed to parse Claude JSON response: %s", text[:500])
        return {}
