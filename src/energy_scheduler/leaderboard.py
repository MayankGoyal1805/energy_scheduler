from __future__ import annotations

from dataclasses import dataclass
from statistics import median
from time import perf_counter
from typing import Any, Callable

from energy_scheduler.config import BenchmarkSettings
from energy_scheduler.models import BenchmarkRun
from energy_scheduler.runner import BenchmarkRunner


@dataclass(slots=True, frozen=True)
class LeaderboardRow:
    label: str
    actual_name: str
    scheduler_mode: str
    sched_ext_scheduler: str | None
    sched_ext_args: str | None
    samples: int
    failed_trials: int
    median_energy_j: float | None
    median_runtime_s: float | None
    median_delta_j: float | None
    median_delta_percent: float | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "actual_name": self.actual_name,
            "scheduler_mode": self.scheduler_mode,
            "sched_ext_scheduler": self.sched_ext_scheduler,
            "sched_ext_args": self.sched_ext_args,
            "samples": self.samples,
            "failed_trials": self.failed_trials,
            "median_energy_j": self.median_energy_j,
            "median_runtime_s": self.median_runtime_s,
            "median_delta_j": self.median_delta_j,
            "median_delta_percent": self.median_delta_percent,
        }


def run_median_leaderboard(
    *,
    runner: BenchmarkRunner,
    workload_name: str,
    task_count: int,
    task_seconds: float,
    repetitions: int,
    trials: int,
    candidates: list[str],
    enable_perf_stat: bool,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    trial_count = max(trials, 1)

    baseline_energy_samples: list[float] = []
    baseline_runtime_samples: list[float] = []
    baseline_failed_trials = 0

    candidate_specs: list[tuple[str, str, str | None]] = [
        (name, name, None) for name in candidates
    ]

    candidate_energy: dict[str, list[float]] = {label: [] for label, _, _ in candidate_specs}
    candidate_runtime: dict[str, list[float]] = {label: [] for label, _, _ in candidate_specs}
    candidate_delta_j: dict[str, list[float]] = {label: [] for label, _, _ in candidate_specs}
    candidate_delta_pct: dict[str, list[float]] = {label: [] for label, _, _ in candidate_specs}
    candidate_failed_trials: dict[str, int] = {label: 0 for label, _, _ in candidate_specs}
    candidate_failure_reasons: dict[str, list[str]] = {label: [] for label, _, _ in candidate_specs}
    baseline_failure_reasons: list[str] = []

    for trial_index in range(1, trial_count + 1):
        _progress(progress_callback, f"[median-board] trial {trial_index}/{trial_count}: baseline linux_default")
        baseline_started = perf_counter()
        baseline, baseline_error = _safe_run(
            runner,
            BenchmarkSettings(
                workload_name=workload_name,
                scheduler_name="linux_default",
                task_count=task_count,
                task_seconds=task_seconds,
                repetitions=repetitions,
                enable_perf_stat=enable_perf_stat,
            ),
        )
        baseline_elapsed = perf_counter() - baseline_started
        if baseline is None:
            baseline_failed_trials += 1
            if baseline_error:
                baseline_failure_reasons.append(baseline_error)
            _progress(
                progress_callback,
                f"[median-board] baseline failed after {baseline_elapsed:.2f}s: {baseline_error or 'unknown error'}",
            )
            for label in candidate_failed_trials:
                candidate_failed_trials[label] += 1
                candidate_failure_reasons[label].append("baseline failed")
            continue

        baseline_energy = _extract_metric(baseline, "rapl", "package_energy_j")
        if baseline_energy is None:
            baseline_failed_trials += 1
            baseline_failure_reasons.append("baseline missing rapl.package_energy_j")
            _progress(
                progress_callback,
                f"[median-board] baseline missing rapl.package_energy_j after {baseline_elapsed:.2f}s",
            )
            for label in candidate_failed_trials:
                candidate_failed_trials[label] += 1
                candidate_failure_reasons[label].append("baseline missing rapl.package_energy_j")
            continue

        _progress(
            progress_callback,
            (
                f"[median-board] baseline ok in {baseline_elapsed:.2f}s "
                f"energy={baseline_energy:.6g}J"
            ),
        )
        baseline_energy_samples.append(baseline_energy)
        baseline_runtime_samples.append(baseline.average_runtime_s)

        for label, sched_name, sched_args in candidate_specs:
            _progress(progress_callback, f"[median-board] trial {trial_index}/{trial_count}: candidate {label}")
            candidate_started = perf_counter()
            candidate, candidate_error = _safe_run(
                runner,
                BenchmarkSettings(
                    workload_name=workload_name,
                    scheduler_name="custom_sched_ext",
                    task_count=task_count,
                    task_seconds=task_seconds,
                    repetitions=repetitions,
                    sched_ext_scheduler=sched_name,
                    sched_ext_args=sched_args,
                    enable_perf_stat=enable_perf_stat,
                ),
            )
            candidate_elapsed = perf_counter() - candidate_started
            if candidate is None:
                candidate_failed_trials[label] += 1
                if candidate_error:
                    candidate_failure_reasons[label].append(candidate_error)
                _progress(
                    progress_callback,
                    (
                        f"[median-board] candidate {label} failed after {candidate_elapsed:.2f}s: "
                        f"{candidate_error or 'unknown error'}"
                    ),
                )
                continue

            energy = _extract_metric(candidate, "rapl", "package_energy_j")
            if energy is None:
                candidate_failed_trials[label] += 1
                candidate_failure_reasons[label].append("candidate missing rapl.package_energy_j")
                _progress(
                    progress_callback,
                    f"[median-board] candidate {label} missing rapl.package_energy_j after {candidate_elapsed:.2f}s",
                )
                continue

            candidate_energy[label].append(energy)
            candidate_runtime[label].append(candidate.average_runtime_s)
            delta_j = energy - baseline_energy
            candidate_delta_j[label].append(delta_j)
            if baseline_energy != 0:
                candidate_delta_pct[label].append((delta_j / baseline_energy) * 100)
            _progress(
                progress_callback,
                (
                    f"[median-board] candidate {label} ok in {candidate_elapsed:.2f}s "
                    f"energy={energy:.6g}J delta={delta_j:.6g}J"
                ),
            )

    rows: list[LeaderboardRow] = []

    rows.append(
        LeaderboardRow(
            label="linux_default",
            actual_name="Linux fair-class scheduler (SCHED_OTHER; CFS/EEVDF)",
            scheduler_mode="linux_default",
            sched_ext_scheduler=None,
            sched_ext_args=None,
            samples=len(baseline_energy_samples),
            failed_trials=baseline_failed_trials,
            median_energy_j=_median_or_none(baseline_energy_samples),
            median_runtime_s=_median_or_none(baseline_runtime_samples),
            median_delta_j=0.0 if baseline_energy_samples else None,
            median_delta_percent=0.0 if baseline_energy_samples else None,
        )
    )

    for label, sched_name, sched_args in candidate_specs:
        rows.append(
            LeaderboardRow(
                label=label,
                actual_name=f"scx_{sched_name}" + (" (tuned)" if sched_args else ""),
                scheduler_mode="custom_sched_ext",
                sched_ext_scheduler=sched_name,
                sched_ext_args=sched_args,
                samples=len(candidate_energy[label]),
                failed_trials=candidate_failed_trials[label],
                median_energy_j=_median_or_none(candidate_energy[label]),
                median_runtime_s=_median_or_none(candidate_runtime[label]),
                median_delta_j=_median_or_none(candidate_delta_j[label]),
                median_delta_percent=_median_or_none(candidate_delta_pct[label]),
            )
        )

    baseline_row = rows[0]
    sortable = [row for row in rows[1:] if row.median_energy_j is not None]
    sortable.sort(key=lambda row: row.median_energy_j or 0.0)
    missing = [row for row in rows[1:] if row.median_energy_j is None]
    ordered_rows = [baseline_row, *sortable, *missing]

    return {
        "workload_name": workload_name,
        "task_count": task_count,
        "task_seconds": task_seconds,
        "repetitions": repetitions,
        "trials": trial_count,
        "enable_perf_stat": enable_perf_stat,
        "rows": [row.to_dict() for row in ordered_rows],
        "failure_reasons": {
            "baseline": _top_reasons(baseline_failure_reasons),
            **{label: _top_reasons(reasons) for label, reasons in candidate_failure_reasons.items()},
        },
    }


def _safe_run(
    runner: BenchmarkRunner,
    settings: BenchmarkSettings,
) -> tuple[BenchmarkRun | None, str | None]:
    try:
        return runner.run(settings), None
    except Exception as error:  # noqa: BLE001
        return None, str(error)


def _extract_metric(run: BenchmarkRun, collector_name: str, metric_name: str) -> float | None:
    for reading in run.collector_readings:
        if reading.collector_name != collector_name:
            continue
        value = reading.metrics.get(metric_name)
        if isinstance(value, (float, int)):
            return float(value)
    return None


def _median_or_none(values: list[float]) -> float | None:
    if not values:
        return None
    return float(median(values))


def _top_reasons(reasons: list[str], limit: int = 3) -> list[str]:
    if not reasons:
        return []
    counts: dict[str, int] = {}
    for reason in reasons:
        counts[reason] = counts.get(reason, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))
    return [f"{reason} (x{count})" for reason, count in ranked[:limit]]


def _progress(callback: Callable[[str], None] | None, message: str) -> None:
    if callback is not None:
        callback(message)
