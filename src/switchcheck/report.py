"""Self-contained HTML reports for persisted replays."""
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from datetime import datetime, timezone
from pathlib import Path
from statistics import fmean, median
from typing import Any

from switchcheck.store import ReportCase, database_path, get_replay, list_report_cases


def write_report(project_directory: Path, *, replay_id: str, output: Path | None = None) -> Path:
    """Render a replay as a portable HTML document and return its absolute path."""
    replay = get_replay(project_directory, replay_id=replay_id)
    if replay is None:
        raise ValueError(f"Replay {replay_id!r} was not found in this project.")
    cases = list_report_cases(project_directory, replay_id=replay_id)
    destination = (
        output or database_path(project_directory).parent / "reports" / f"{replay_id}.html"
    )
    destination = destination.resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _render(replay, cases, database_path(project_directory)), encoding="utf-8"
    )
    return destination


def _render(replay: Any, cases: list[ReportCase], database: Path) -> str:
    passed = sum(case.result.passed is True for case in cases)
    provider_errors = sum(case.result.error is not None for case in cases)
    evaluation_failures = sum(
        case.result.passed is False and case.result.error is None for case in cases
    )
    pass_rate = passed / len(cases) if cases else 0
    comparison = _comparison_table(replay, cases, pass_rate)
    cards = "".join(_case_card(case, index + 1) for index, case in enumerate(cases))
    if not cards:
        cards = '<p class="empty">This replay has no results.</p>'
    metadata = [
        ("Replay ID", replay.id),
        ("Created", replay.created_at),
        ("Candidate model", replay.target_model),
        ("Tag filter", replay.tag or "All recorded runs"),
        ("Checks", _json(replay.checkers)),
        ("Replay parameters", _json(replay.params)),
        ("Package version", replay.package_version),
        ("Database", str(database)),
        ("Report generated", datetime.now(timezone.utc).isoformat()),
    ]
    metadata_html = "".join(
        f"<dt>{_escape(label)}</dt><dd><code>{_escape(value)}</code></dd>"
        for label, value in metadata
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Switchcheck replay report</title><style>
:root {{ color-scheme: light dark; font-family: system-ui, sans-serif; }}
body {{ max-width: 1120px; margin: 2rem auto; padding: 0 1rem; line-height: 1.45; }}
h1 {{ margin-bottom: .15rem; }} .subtle {{ color: #68707a; }}
.metrics {{ display:grid; grid-template-columns:repeat(4, minmax(120px, 1fr)); gap: .75rem; margin:1.5rem 0; }}
.metric, .case {{ border:1px solid #9aa4ad; border-radius:8px; padding:1rem; }} .metric strong {{ display:block; font-size:1.6rem; }}
.case {{ margin: 1rem 0; }} .case.fail {{ border-left: 5px solid #c43b3b; }} .case.pass {{ border-left: 5px solid #25834c; }}
.status {{ font-weight:700; }} .fail .status {{ color:#c43b3b; }} .pass .status {{ color:#25834c; }}
.outputs {{ display:grid; grid-template-columns:1fr 1fr; gap:1rem; }} pre {{ overflow:auto; white-space:pre-wrap; background:#1f2328; color:#f0f4f8; padding:.8rem; border-radius:5px; }}
dl {{ display:grid; grid-template-columns:max-content 1fr; gap:.45rem 1rem; }} dt {{ font-weight:700; }} dd {{ margin:0; overflow-wrap:anywhere; }}
table {{ width:100%; border-collapse:collapse; }} th,td {{ padding:.5rem; text-align:left; border-bottom:1px solid #9aa4ad; vertical-align:top; }}
.table-scroll {{ overflow-x:auto; }}
@media (max-width: 700px) {{ .metrics, .outputs {{ grid-template-columns:1fr; }} }}
</style></head><body>
<h1>Switchcheck replay report</h1><p class="subtle">Failures appear first. This file is self-contained; treat it as sensitive because it contains recorded outputs.</p>
<section class="metrics" aria-label="Replay summary">
<div class="metric"><span>Cases</span><strong>{len(cases)}</strong></div>
<div class="metric"><span>Passed</span><strong>{passed} ({pass_rate:.0%})</strong></div>
<div class="metric"><span>Evaluation failures</span><strong>{evaluation_failures}</strong></div>
<div class="metric"><span>Provider errors</span><strong>{provider_errors}</strong></div></section>
<h2>Performance comparison</h2>{comparison}
<h2>Cases</h2>{cards}<footer><h2>Reproducibility</h2><dl>{metadata_html}</dl></footer></body></html>"""


def _comparison_table(replay: Any, cases: list[ReportCase], pass_rate: float) -> str:
    source_models = ", ".join(sorted({case.run.model for case in cases})) or "Unavailable"
    rows = [
        ("Model", source_models, replay.target_model),
        (
            "Average latency",
            _latency([case.run.latency_ms for case in cases], average=True),
            _latency([case.result.latency_ms for case in cases], average=True),
        ),
        (
            "Median latency",
            _latency([case.run.latency_ms for case in cases], average=False),
            _latency([case.result.latency_ms for case in cases], average=False),
        ),
        (
            "Total input tokens",
            _total([case.run.input_tokens for case in cases]),
            _total([case.result.input_tokens for case in cases]),
        ),
        (
            "Total output tokens",
            _total([case.run.output_tokens for case in cases]),
            _total([case.result.output_tokens for case in cases]),
        ),
        (
            "Total provider cost",
            _cost([case.run.cost_usd for case in cases]),
            _cost([case.result.cost_usd for case in cases]),
        ),
        ("Pass rate", "Reference", f"{pass_rate:.0%}"),
    ]
    body = "".join(
        f'<tr><th scope="row">{_escape(label)}</th>'
        f"<td>{_escape(source)}</td><td>{_escape(candidate)}</td></tr>"
        for label, source, candidate in rows
    )
    return (
        '<div class="table-scroll"><table aria-label="Source and candidate performance">'
        "<thead><tr><th>Metric</th><th>Recorded source</th><th>Candidate</th></tr></thead>"
        f"<tbody>{body}</tbody></table></div>"
        '<p class="subtle">Unavailable means at least one selected call did not report that '
        "measurement. Candidate latency includes the provider call and Switchcheck overhead.</p>"
    )


def _case_card(case: ReportCase, number: int) -> str:
    result = case.result
    status = "Passed" if result.passed is True else "Provider error" if result.error else "Failed"
    css = "pass" if result.passed is True else "fail"
    verdict_rows = (
        "".join(
            "<tr>"
            f"<td>{_escape(_checker_label(verdict))}</td>"
            f"<td>{'Pass' if verdict.get('passed') else 'Fail'}</td>"
            f"<td>{_escape(str(verdict.get('reason', '')))}</td></tr>"
            for verdict in (result.verdict or [])
        )
        or '<tr><td colspan="3">No deterministic checks configured.</td></tr>'
    )
    candidate = _output(result.output_text, result.output_json, result.error)
    reference = _output(case.run.output_text, case.run.output_json, case.run.error)
    return f"""<article class="case {css}"><h3>Case {number} <span class="status">{status}</span></h3>
<p class="subtle">Run <code>{_escape(case.run.id)}</code> &middot; source <code>{_escape(case.run.model)}</code> &middot; score {_escape(str(result.score if result.score is not None else "-"))} &middot; candidate latency {_escape(str(result.latency_ms if result.latency_ms is not None else "-"))} ms</p>
<div class="outputs"><section><h4>Recorded output</h4><pre>{_escape(reference)}</pre></section><section><h4>Candidate output</h4><pre>{_escape(candidate)}</pre></section></div>
<h4>Checks</h4><table><thead><tr><th>Checker</th><th>Result</th><th>Reason</th></tr></thead><tbody>{verdict_rows}</tbody></table></article>"""


def _output(text: str | None, value: Any | None, error: str | None) -> str:
    if error:
        return f"Error: {error}"
    if value is not None:
        return _json(value)
    return text if text is not None else "(no output)"


def _checker_label(verdict: dict[str, Any]) -> str:
    checker = str(verdict.get("checker", "unknown"))
    details = verdict.get("details")
    if checker == "json-field" and isinstance(details, dict):
        path = details.get("path")
        if isinstance(path, str) and path:
            return f"{checker}:{path}"
    return checker


def _latency(values: list[int | None], *, average: bool) -> str:
    if not values or any(value is None for value in values):
        return "Unavailable"
    measurements = [value for value in values if value is not None]
    result = fmean(measurements) if average else median(measurements)
    return f"{result:,.0f} ms"


def _total(values: list[int | None]) -> str:
    if not values or any(value is None for value in values):
        return "Unavailable"
    return f"{sum(value for value in values if value is not None):,}"


def _cost(values: list[float | None]) -> str:
    if not values or any(value is None for value in values):
        return "Unavailable"
    return f"${sum(value for value in values if value is not None):,.6f}"


def _json(value: Any) -> str:
    return json.dumps(value, indent=2, ensure_ascii=False, sort_keys=True)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
