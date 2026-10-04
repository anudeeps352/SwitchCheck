"""Self-contained reports for labeled dataset experiments."""
# ruff: noqa: E501

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from switchcheck.metrics import ExperimentMetrics, calculate_metrics
from switchcheck.store import (
    EvaluationCase,
    EvaluationResult,
    database_path,
    get_dataset,
    get_experiment,
    list_evaluation_cases,
    list_evaluation_results,
)


def write_experiment_report(
    project_directory: Path, *, experiment_id: str, output: Path | None = None
) -> Path:
    """Render one persisted experiment and return the absolute report path."""
    experiment = get_experiment(project_directory, experiment_id=experiment_id)
    if experiment is None:
        raise ValueError(f"Experiment {experiment_id!r} was not found in this project.")
    dataset = get_dataset(project_directory, identifier=experiment.dataset_id)
    if dataset is None:
        raise ValueError("The experiment dataset was not found.")
    cases = list_evaluation_cases(project_directory, dataset_id=dataset.id)
    results = list_evaluation_results(project_directory, experiment_id=experiment.id)
    metrics = calculate_metrics(cases, results)
    destination = (
        output
        or database_path(project_directory).parent / "reports" / f"experiment-{experiment_id}.html"
    ).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(
        _render(
            experiment_id=experiment.id,
            dataset_name=dataset.name,
            target_model=experiment.target_model,
            evaluator_config=experiment.evaluator_config,
            metrics=metrics,
            cases=cases,
            results=results,
        ),
        encoding="utf-8",
    )
    return destination


def _render(
    *,
    experiment_id: str,
    dataset_name: str,
    target_model: str,
    evaluator_config: dict[str, Any],
    metrics: ExperimentMetrics,
    cases: list[EvaluationCase],
    results: list[EvaluationResult],
) -> str:
    case_by_id = {case.id: case for case in cases}
    cards = "".join(_case_card(case_by_id[result.case_id], result) for result in results)
    optional_metrics = []
    if metrics.field_accuracy is not None:
        optional_metrics.append(("Field accuracy", f"{metrics.field_accuracy:.0%}"))
    if metrics.tool_name_accuracy is not None:
        optional_metrics.append(("Tool accuracy", f"{metrics.tool_name_accuracy:.0%}"))
    if metrics.argument_accuracy is not None:
        optional_metrics.append(("Argument accuracy", f"{metrics.argument_accuracy:.0%}"))
    metric_cards = "".join(
        f'<div class="metric"><span>{_escape(label)}</span><strong>{_escape(value)}</strong></div>'
        for label, value in optional_metrics
    )
    classification = _classification(metrics)
    states = metrics.state_counts
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Switchcheck experiment report</title><style>
:root {{ font-family:system-ui,sans-serif; color-scheme:light dark }}
body {{ max-width:1100px; margin:2rem auto; padding:0 1rem; line-height:1.45 }}
.metrics {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(130px,1fr)); gap:.7rem }}
.metric,.case {{ border:1px solid #89939d; border-radius:8px; padding:1rem }}
.metric strong {{ display:block; font-size:1.5rem }} .case {{ margin:1rem 0 }}
.PASS {{ border-left:5px solid #25834c }} .FAIL {{ border-left:5px solid #c43b3b }}
.REVIEW {{ border-left:5px solid #b7791f }} .ERROR {{ border-left:5px solid #7b3fc6 }}
pre {{ white-space:pre-wrap; overflow:auto; background:#1f2328; color:#f0f4f8; padding:.75rem }}
table {{ width:100%; border-collapse:collapse }} th,td {{ padding:.45rem; border-bottom:1px solid #89939d; text-align:left }}
</style></head><body><h1>Switchcheck experiment</h1>
<p>Dataset <strong>{_escape(dataset_name)}</strong> · candidate <code>{_escape(target_model)}</code></p>
<section class="metrics"><div class="metric"><span>Cases</span><strong>{metrics.case_count}</strong></div>
<div class="metric"><span>Pass rate</span><strong>{metrics.pass_rate:.0%}</strong></div>
<div class="metric"><span>PASS</span><strong>{states["PASS"]}</strong></div>
<div class="metric"><span>FAIL</span><strong>{states["FAIL"]}</strong></div>
<div class="metric"><span>REVIEW</span><strong>{states["REVIEW"]}</strong></div>
<div class="metric"><span>ERROR</span><strong>{states["ERROR"]}</strong></div>{metric_cards}</section>
{classification}<h2>Cases</h2>{cards or "<p>No results.</p>"}
<footer><h2>Reproducibility</h2><p>Experiment <code>{_escape(experiment_id)}</code></p>
<pre>{_escape(_json(evaluator_config))}</pre></footer></body></html>"""


def _case_card(case: EvaluationCase, result: EvaluationResult) -> str:
    rows = "".join(
        f"<tr><td>{_escape(str(item.get('evaluator', 'unknown')))}</td>"
        f"<td>{_escape(str(item.get('state', '')))}</td>"
        f"<td>{_escape(str(item.get('reason', '')))}</td></tr>"
        for item in result.verdict or []
    )
    candidate = result.output_json if result.output_json is not None else result.output_text
    return f"""<article class="case {_escape(result.state or "ERROR")}">
<h3>{_escape(result.state or "ERROR")} · {_escape(case.task_type.value if case.task_type else "legacy")}</h3>
<p><code>{_escape(case.id)}</code> · score {_escape(str(result.score))}</p>
<h4>Input</h4><pre>{_escape(_json(case.messages))}</pre>
<h4>Expected</h4><pre>{_escape(_json(case.expected))}</pre>
<h4>Candidate</h4><pre>{_escape(_json(candidate))}</pre>
<table><thead><tr><th>Evaluator</th><th>State</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table>
</article>"""


def _classification(metrics: ExperimentMetrics) -> str:
    if not metrics.classification:
        return ""
    sections = []
    for field, values in metrics.classification.items():
        rows = "".join(
            f"<tr><td>{_escape(label)}</td><td>{scores['precision']:.2f}</td>"
            f"<td>{scores['recall']:.2f}</td><td>{scores['f1']:.2f}</td></tr>"
            for label, scores in values.per_label.items()
        )
        sections.append(
            f"<h3>{_escape(field)} · accuracy {values.accuracy:.0%}</h3>"
            f"<table><tr><th>Label</th><th>Precision</th><th>Recall</th><th>F1</th></tr>{rows}</table>"
        )
    return "<h2>Classification metrics</h2>" + "".join(sections)


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)


def _escape(value: str) -> str:
    return html.escape(value, quote=True)
