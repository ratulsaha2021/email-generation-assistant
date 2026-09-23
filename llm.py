"""Minimal Ollama chat client shared by generation and evaluation."""

from __future__ import annotations

import json
import time
from typing import Any

import requests

from constants import OLLAMA_HOST, SEED


class OllamaError(RuntimeError):
    """Raised when Ollama is unreachable or returns an unusable response."""


def ensure_models_available(*models: str) -> None:
    """Fail fast with an actionable message if Ollama or a model is missing."""
    try:
        resp = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=10)
        resp.raise_for_status()
    except requests.exceptions.RequestException as exc:
        raise OllamaError(
            f"Cannot reach Ollama at {OLLAMA_HOST}. Start it with `ollama serve`."
        ) from exc

    installed = {m["name"] for m in resp.json().get("models", [])}
    missing = [m for m in models if m not in installed]
    if missing:
        raise OllamaError(
            f"Model(s) not installed: {', '.join(missing)}. "
            f"Installed: {', '.join(sorted(installed)) or 'none'}. "
            f"Run `ollama pull <model>` or set GENERATOR_MODEL / JUDGE_MODEL."
        )


def chat(
    model: str,
    messages: list[dict[str, str]],
    temperature: float,
    response_format: dict[str, Any] | None = None,
    retries: int = 3,
    timeout: int = 600,
) -> str:
    """Send a non-streaming chat request and return the assistant text."""
    payload: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "stream": False,
        "think": False,
        "keep_alive": "15m",
        # Sampling parameters must live under "options"; top-level keys are ignored.
        "options": {"temperature": temperature, "seed": SEED},
    }
    if response_format is not None:
        payload["format"] = response_format

    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            resp = requests.post(f"{OLLAMA_HOST}/api/chat", json=payload, timeout=timeout)
            resp.raise_for_status()
            content = resp.json()["message"]["content"].strip()
            if content:
                return content
            last_error = OllamaError("Empty response from model")
        except requests.exceptions.ConnectionError as exc:
            raise OllamaError(
                f"Cannot connect to Ollama at {OLLAMA_HOST}. Start it with `ollama serve`."
            ) from exc
        except (requests.exceptions.RequestException, KeyError, ValueError) as exc:
            last_error = exc
        time.sleep(2**attempt)
    raise OllamaError(f"Ollama request failed after {retries} attempts: {last_error}")


def chat_json(
    model: str,
    messages: list[dict[str, str]],
    schema: dict[str, Any],
    temperature: float,
) -> dict[str, Any]:
    """Chat with a JSON schema constraint and return the parsed object."""
    text = chat(model, messages, temperature, response_format=schema)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise OllamaError(f"Judge returned invalid JSON: {text[:200]}") from exc
