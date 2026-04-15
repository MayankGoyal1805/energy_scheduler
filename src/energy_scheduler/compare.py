from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from energy_scheduler.models import BenchmarkRun


@dataclass(slots=True, frozen=True)
class MetricComparison:
    metric: str
    baseline: float | int | str
    candidate: float | int | str
    delta: float | None
    delta_percent: float | None


@dataclass(slots=True, frozen=True)
class ComparisonResult:
    baseline: BenchmarkRun
    candidate: BenchmarkRun
    metrics: tuple[MetricComparison, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "baseline": {
                "run_id": self.baseline.run_id,
                "scheduler_name": self.baseline.scheduler_name,
                "workload_name": self.baseline.workload_name,
            },
            "candidate": {
                "run_id": self.candidate.run_id,
                "scheduler_name": self.candidate.scheduler_name,
                "workload_name": self.candidate.workload_name,
            },
            "metrics": [
                {
                    "metric": metric.metric,
                    "baseline": metric.baseline,
                    "candidate": metric.candidate,
                    "delta": metric.delta,
                    "delta_percent": metric.delta_percent,
                }
                for metric in self.metrics
            ],
        }


def compare_runs(baseline: BenchmarkRun, candidate: BenchmarkRun) -> ComparisonResult:
    metrics: list[MetricComparison] = [
        _compare_metric(
            "average_runtime_s",
            baseline.average_runtime_s,
            candidate.average_runtime_s,
        ),
        _compare_metric(
            "average_waiting_time_s",
            baseline.average_waiting_time_s,
            candidate.average_waiting_time_s,
        ),
        _compare_metric(
            "average_turnaround_time_s",
            baseline.average_turnaround_time_s,
            candidate.average_turnaround_time_s,
        ),
        _compare_metric(
            "average_response_time_s",
            baseline.average_response_time_s,
            candidate.average_response_time_s,
        ),
        _compare_metric(
            "context_switches",
            _extract_context_switches(baseline),
            _extract_context_switches(candidate),
        ),
        _compare_metric(
            "rapl_package_energy_j",
            _extract_metric(baseline, "rapl", "package_energy_j"),
            _extract_metric(candidate, "rapl", "package_energy_j"),
        ),
    ]

    baseline_estimated = _extract_metric(
        baseline,
        "custom_simulated_scheduler",
        "estimated_energy_units",
    )
    candidate_estimated = _extract_metric(
        candidate,
        "custom_simulated_scheduler",
        "estimated_energy_units",
    )
    if baseline_estimated is not None or candidate_estimated is not None:
        metrics.append(
            _compare_metric(
                "estimated_energy_units",
                baseline_estimated,
                candidate_estimated,
            )
        )

    return ComparisonResult(baseline=baseline, candidate=candidate, metrics=tuple(metrics))


def format_comparison_table(result: ComparisonResult) -> str:
    rows = [
        ("metric", "baseline", "candidate", "delta", "delta %"),
        *(
            (
                metric.metric,
                _format_value(metric.baseline),
                _format_value(metric.candidate),
                _format_optional(metric.delta),
                _format_optional(metric.delta_percent),
            )
            for metric in result.metrics
        ),
    ]
    widths = [max(len(row[column]) for row in rows) for column in range(len(rows[0]))]
    lines = []
    for index, row in enumerate(rows):
        lines.append(
            "  ".join(value.ljust(widths[column]) for column, value in enumerate(row))
        )
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _compare_metric(
    metric: str,
    baseline: float | int | str | None,
    candidate: float | int | str | None,
) -> MetricComparison:
    baseline_value = "n/a" if baseline is None else baseline
    candidate_value = "n/a" if candidate is None else candidate
    if isinstance(baseline, (float, int)) and isinstance(candidate, (float, int)):
        delta = candidate - baseline
        delta_percent = None if baseline == 0 else (delta / baseline) * 100
    else:
        delta = None
        delta_percent = None
    return MetricComparison(
        metric=metric,
        baseline=baseline_value,
        candidate=candidate_value,
        delta=delta,
        delta_percent=delta_percent,
    )


def _extract_context_switches(run: BenchmarkRun) -> int | None:
    simulated = _collector_metrics(run, "custom_simulated_scheduler")
    if simulated is not None:
        value = simulated.get("context_switches")
        if isinstance(value, int):
            return value

    child_usage = _collector_metrics(run, "child_process_usage")
    if child_usage is not None:
        voluntary = child_usage.get("voluntary_context_switches")
        involuntary = child_usage.get("involuntary_context_switches")
        if isinstance(voluntary, int) and isinstance(involuntary, int):
            return voluntary + involuntary
    return None


def _extract_metric(run: BenchmarkRun, collector_name: str, metric_name: str) -> float | int | str | None:
    metrics = _collector_metrics(run, collector_name)
    if metrics is None:
        return None
    value = metrics.get(metric_name)
    if isinstance(value, (float, int, str)):
        return value
    return None


def _collector_metrics(run: BenchmarkRun, collector_name: str) -> dict[str, float | int | str] | None:
    for reading in run.collector_readings:
        if reading.collector_name == collector_name:
            return reading.metrics
    return None


def _format_value(value: float | int | str) -> str:
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def _format_optional(value: float | None) -> str:
    if value is None:
        return "n/a"
    return f"{value:.6g}"
