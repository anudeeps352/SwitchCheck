"""Application-facing wrapper that records LiteLLM chat completions."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from time import perf_counter
from typing import Any

from switchcheck.store import create_run

Completion = Callable[..., Any]


def chat(
    *,
    model: str,
    messages: list[dict[str, Any]],
    tag: str | None = None,
    project_directory: Path = Path("."),
    completion: Completion | None = None,
    **params: Any,
) -> Any:
    """Call a provider and record its response or error before returning/raising.

    ``completion`` is primarily an offline-test seam. In normal use LiteLLM's
    ``completion`` function is loaded lazily, so importing Switchcheck never
    requires provider dependencies or credentials.
    """
    normalized_messages = _normalize_messages(messages)
    normalized_params = dict(params)
    tools = normalized_params.pop("tools", None)
    provider_completion = completion or _load_litellm_completion()
    started = perf_counter()
    try:
        response = provider_completion(
            model=model, messages=normalized_messages, tools=tools, **normalized_params
        )
    except Exception as error:
        create_run(
            project_directory,
            model=model,
            messages=normalized_messages,
            params=normalized_params,
            tag=tag,
            tools=tools,
            latency_ms=_elapsed_ms(started),
            error=f"{type(error).__name__}: {error}",
        )
        raise

    output_text, output_json, input_tokens, output_tokens, cost_usd = _response_fields(response)
    create_run(
        project_directory,
        model=model,
        messages=normalized_messages,
        params=normalized_params,
        tag=tag,
        tools=tools,
        output_text=output_text,
        output_json=output_json,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=_elapsed_ms(started),
    )
    return response


def _load_litellm_completion() -> Completion:
    try:
        from litellm import completion
    except ImportError as error:
        raise RuntimeError(
            "LiteLLM is required for provider calls. "
            "Install Switchcheck with its provider dependency."
        ) from error
    return completion


def _normalize_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not messages:
        raise ValueError("messages must contain at least one message")
    normalized: list[dict[str, Any]] = []
    for message in messages:
        if not isinstance(message, dict) or not isinstance(message.get("role"), str):
            raise ValueError("each message must be a mapping with a string role")
        normalized.append(dict(message))
    return normalized


def _response_fields(
    response: Any,
) -> tuple[str | None, Any | None, int | None, int | None, float | None]:
    data = response if isinstance(response, dict) else getattr(response, "model_dump", lambda: {})()
    choices = data.get("choices", []) if isinstance(data, dict) else []
    message = choices[0].get("message", {}) if choices and isinstance(choices[0], dict) else {}
    content = message.get("content") if isinstance(message, dict) else None
    usage = data.get("usage", {}) if isinstance(data, dict) else {}
    return (
        content if isinstance(content, str) else None,
        _json_content(content),
        _integer(usage.get("prompt_tokens")),
        _integer(usage.get("completion_tokens")),
        _number(data.get("_hidden_params", {}).get("response_cost"))
        if isinstance(data, dict)
        else None,
    )


def _json_content(content: Any) -> Any | None:
    """Decode a JSON assistant message when one was returned."""
    if not isinstance(content, str):
        return None
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        return None


def _integer(value: Any) -> int | None:
    return value if isinstance(value, int) else None


def _number(value: Any) -> float | None:
    return float(value) if isinstance(value, (int, float)) else None


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
