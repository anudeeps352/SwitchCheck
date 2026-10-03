"""Replay recorded calls against a candidate provider configuration."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter, sleep
from typing import Any

from switchcheck.client import Completion, _load_litellm_completion, _response_fields
from switchcheck.store import (
    ReplayResult,
    Run,
    create_replay,
    create_replay_result,
    list_runs,
    update_replay_result,
)


@dataclass(frozen=True)
class ReplaySummary:
    """Persisted replay outcome, including failures that need review."""

    replay_id: str
    selected_count: int
    completed_count: int
    failed_count: int
    estimated_cost_usd: None = None


def replay(
    project_directory: Path,
    *,
    target_model: str,
    tag: str | None = None,
    limit: int = 20,
    concurrency: int = 1,
    attempts: int = 3,
    completion: Completion | None = None,
) -> ReplaySummary:
    """Run selected calls concurrently and persist every terminal provider outcome."""
    if concurrency < 1:
        raise ValueError("concurrency must be at least 1")
    if attempts < 1:
        raise ValueError("attempts must be at least 1")
    runs = list_runs(project_directory, tag=tag, limit=limit)
    replay_id = create_replay(project_directory, target_model=target_model, tag=tag, params={})
    pending = [
        (run, create_replay_result(project_directory, replay_id=replay_id, run_id=run.id))
        for run in runs
    ]
    if not pending:
        return _summary(replay_id, 0, [])
    provider_completion = completion or _load_litellm_completion()
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = [
            executor.submit(
                _replay_one,
                project_directory,
                run,
                result,
                target_model,
                provider_completion,
                attempts,
            )
            for run, result in pending
        ]
        completed = [future.result() for future in futures]
    return _summary(replay_id, len(runs), completed)


def replay_dry_run(project_directory: Path, *, tag: str | None = None, limit: int = 20) -> int:
    """Return selection size without creating a replay or contacting a provider."""
    return len(list_runs(project_directory, tag=tag, limit=limit))


def _replay_one(
    project_directory: Path,
    run: Run,
    result: ReplayResult,
    target_model: str,
    completion: Completion,
    attempts: int,
) -> ReplayResult:
    started = perf_counter()
    try:
        response = _call_with_retry(completion, target_model, run, attempts)
    except Exception as error:
        return update_replay_result(
            project_directory,
            result_id=result.id,
            latency_ms=_elapsed_ms(started),
            error=f"{type(error).__name__}: {error}",
        )
    output_text, output_json, input_tokens, output_tokens, cost_usd = _response_fields(response)
    return update_replay_result(
        project_directory,
        result_id=result.id,
        output_text=output_text,
        output_json=output_json,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd,
        latency_ms=_elapsed_ms(started),
    )


def _call_with_retry(completion: Completion, target_model: str, run: Run, attempts: int) -> Any:
    kwargs = {"model": target_model, "messages": run.messages, **run.params}
    if run.tools is not None:
        kwargs["tools"] = run.tools
    for attempt in range(attempts):
        try:
            return completion(**kwargs)
        except (ConnectionError, TimeoutError):
            if attempt == attempts - 1:
                raise
            sleep(0.1 * (2**attempt))
    raise AssertionError("unreachable")


def _summary(replay_id: str, selected_count: int, results: list[ReplayResult]) -> ReplaySummary:
    return ReplaySummary(
        replay_id=replay_id,
        selected_count=selected_count,
        completed_count=sum(result.error is None for result in results),
        failed_count=sum(result.error is not None for result in results),
    )


def _elapsed_ms(started: float) -> int:
    return round((perf_counter() - started) * 1000)
