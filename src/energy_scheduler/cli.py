from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from energy_scheduler.compare import compare_runs, format_comparison_table
from energy_scheduler.config import AppPaths, BenchmarkSettings
from energy_scheduler.doctor import format_doctor_report, run_doctor
from energy_scheduler.leaderboard import run_median_leaderboard
from energy_scheduler.runner import BenchmarkRunner
from energy_scheduler.storage import BenchmarkStore, StoredRunSummary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="energy-scheduler",
        description="Run synthetic scheduler benchmarks and store the results.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("workloads", help="List available synthetic workloads.")

    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Check kernel, sched_ext, perf, RAPL, and required tools.",
    )
    doctor_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )

    run_parser = subparsers.add_parser("run", help="Execute a benchmark run.")
    run_parser.add_argument("--workload", default="cpu_bound", help="Workload name to run.")
    run_parser.add_argument(
        "--scheduler",
        default="linux_default",
        help="Scheduler adapter to use.",
    )
    run_parser.add_argument(
        "--sched-ext-scheduler",
        default="cake",
        help="Installed sched_ext scheduler to use when --scheduler custom_sched_ext.",
    )
    run_parser.add_argument(
        "--sched-ext-args",
        default=None,
        help="Optional argument string passed to sched_ext scheduler via scxctl --args.",
    )
    run_parser.add_argument("--tasks", type=int, default=4, help="Number of tasks.")
    run_parser.add_argument(
        "--task-seconds",
        type=float,
        default=0.25,
        help="CPU time budget per CPU burst.",
    )
    run_parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repeated workload runs.",
    )
    run_parser.add_argument(
        "--db",
        type=Path,
        default=AppPaths.default().database_path,
        help="SQLite database path for persisted runs.",
    )
    run_parser.add_argument(
        "--save",
        action="store_true",
        help="Persist the run into SQLite.",
    )
    run_parser.add_argument(
        "--perf-stat",
        action="store_true",
        help="Collect perf stat counters for the benchmark window.",
    )

    compare_parser = subparsers.add_parser(
        "compare",
        help="Run linux_default and custom_simulated with the same workload.",
    )
    compare_parser.add_argument("--workload", default="cpu_bound", help="Workload name to run.")
    compare_parser.add_argument("--tasks", type=int, default=4, help="Number of tasks.")
    compare_parser.add_argument(
        "--task-seconds",
        type=float,
        default=0.25,
        help="CPU time budget per CPU burst.",
    )
    compare_parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repeated workload runs.",
    )
    compare_parser.add_argument(
        "--db",
        type=Path,
        default=AppPaths.default().database_path,
        help="SQLite database path for persisted runs.",
    )
    compare_parser.add_argument(
        "--save",
        action="store_true",
        help="Persist both runs into SQLite.",
    )
    compare_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )
    compare_parser.add_argument(
        "--candidate-scheduler",
        default="custom_simulated",
        choices=("custom_simulated", "custom_sched_ext"),
        help="Candidate scheduler to compare against linux_default.",
    )
    compare_parser.add_argument(
        "--sched-ext-scheduler",
        default="cake",
        help="Installed sched_ext scheduler to use when candidate is custom_sched_ext.",
    )
    compare_parser.add_argument(
        "--sched-ext-args",
        default=None,
        help="Optional argument string passed to candidate sched_ext scheduler via scxctl --args.",
    )
    compare_parser.add_argument(
        "--perf-stat",
        action="store_true",
        help="Collect perf stat counters for baseline and candidate runs.",
    )

    search_parser = subparsers.add_parser(
        "search-energy",
        help="Sweep installed sched_ext candidates and find lower-energy runs vs linux_default.",
    )
    search_parser.add_argument("--workload", default="cpu_bound", help="Workload name to run.")
    search_parser.add_argument("--tasks", type=int, default=4, help="Number of tasks.")
    search_parser.add_argument(
        "--task-seconds",
        type=float,
        default=0.25,
        help="CPU time budget per CPU burst.",
    )
    search_parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repeated workload runs.",
    )
    search_parser.add_argument(
        "--candidates",
        default="cake,lavd,flash,bpfland,cosmos,p2dq,tickless,rustland,rusty,beerland,pandemonium",
        help="Comma-separated sched_ext scheduler names to evaluate.",
    )
    search_parser.add_argument(
        "--db",
        type=Path,
        default=AppPaths.default().database_path,
        help="SQLite database path for persisted runs.",
    )
    search_parser.add_argument(
        "--save",
        action="store_true",
        help="Persist baseline and successful candidate runs into SQLite.",
    )
    search_parser.add_argument(
        "--perf-stat",
        action="store_true",
        help="Collect perf stat counters for baseline and candidate runs.",
    )

    median_parser = subparsers.add_parser(
        "median-board",
        help="Build a median leaderboard of linux_default vs sched_ext candidates.",
    )
    median_parser.add_argument("--workload", default="cpu_bound", help="Workload name to run.")
    median_parser.add_argument("--tasks", type=int, default=4, help="Number of tasks.")
    median_parser.add_argument(
        "--task-seconds",
        type=float,
        default=0.25,
        help="CPU time budget per CPU burst.",
    )
    median_parser.add_argument(
        "--repetitions",
        type=int,
        default=1,
        help="Number of repeated workload runs in each trial.",
    )
    median_parser.add_argument(
        "--trials",
        type=int,
        default=5,
        help="Number of baseline+candidate trial cycles used for median aggregation.",
    )
    median_parser.add_argument(
        "--candidates",
        default="cake,lavd,flash,bpfland,cosmos,p2dq,tickless,rustland,rusty,beerland,pandemonium",
        help="Comma-separated sched_ext scheduler names to evaluate.",
    )
    median_parser.add_argument(
        "--progress",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Show per-trial and per-candidate progress logs to stderr (use --no-progress to disable).",
    )
    median_parser.add_argument(
        "--perf-stat",
        action="store_true",
        help="Collect perf stat counters for baseline and candidate runs.",
    )
    median_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON instead of a table.",
    )

    results_parser = subparsers.add_parser(
        "results",
        help="List saved benchmark runs or print a single saved run payload.",
    )
    results_parser.add_argument(
        "--db",
        type=Path,
        default=AppPaths.default().database_path,
        help="SQLite database path for persisted runs.",
    )
    results_parser.add_argument(
        "--limit",
        type=int,
        default=20,
        help="Maximum number of rows returned when listing runs.",
    )
    results_parser.add_argument(
        "--scheduler",
        help="Filter saved runs by scheduler name.",
    )
    results_parser.add_argument(
        "--workload",
        help="Filter saved runs by workload name.",
    )
    results_parser.add_argument(
        "--run-id",
        help="If provided, print the full JSON payload for a single run.",
    )
    results_parser.add_argument(
        "--json",
        action="store_true",
        help="Print machine-readable JSON output.",
    )
    results_parser.add_argument(
        "--from-time",
        help="Inclusive lower timestamp bound for created_at filtering (ISO or SQLite text).",
    )
    results_parser.add_argument(
        "--to-time",
        help="Inclusive upper timestamp bound for created_at filtering (ISO or SQLite text).",
    )
    results_parser.add_argument(
        "--sort-by",
        default="created_at",
        choices=(
            "created_at",
            "workload_name",
            "scheduler_name",
            "task_count",
            "task_seconds",
            "repetitions",
            "average_runtime_s",
        ),
        help="Sort key for listing saved runs.",
    )
    results_parser.add_argument(
        "--sort-order",
        default="desc",
        choices=("asc", "desc"),
        help="Sort direction for listing saved runs.",
    )

    serve_parser = subparsers.add_parser(
        "serve",
        help="Start the local FastAPI service for UI/API clients.",
    )
    serve_parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind.")
    serve_parser.add_argument("--port", type=int, default=8000, help="TCP port to bind.")
    serve_parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable autoreload for local development.",
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    runner = BenchmarkRunner()

    if args.command == "workloads":
        for workload_name in runner.available_workloads():
            print(workload_name)
        return

    if args.command == "doctor":
        report = run_doctor()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(format_doctor_report(report))
        return

    if args.command == "compare":
        baseline_settings = BenchmarkSettings(
            workload_name=args.workload,
            scheduler_name="linux_default",
            task_count=args.tasks,
            task_seconds=args.task_seconds,
            repetitions=args.repetitions,
            enable_perf_stat=args.perf_stat,
        )
        candidate_settings = BenchmarkSettings(
            workload_name=args.workload,
            scheduler_name=args.candidate_scheduler,
            task_count=args.tasks,
            task_seconds=args.task_seconds,
            repetitions=args.repetitions,
            sched_ext_scheduler=args.sched_ext_scheduler,
            sched_ext_args=args.sched_ext_args,
            enable_perf_stat=args.perf_stat,
        )
        baseline = runner.run(baseline_settings)
        candidate = runner.run(candidate_settings)
        comparison = compare_runs(baseline, candidate)

        if args.json:
            print(json.dumps(comparison.to_dict(), indent=2))
        else:
            baseline_label = baseline.scheduler_name
            candidate_label = candidate.scheduler_name
            if args.candidate_scheduler == "custom_sched_ext":
                candidate_label = f"{candidate.scheduler_name}({args.sched_ext_scheduler})"
            print(f"Workload: {args.workload}")
            print(f"Baseline: {baseline_label} ({baseline.run_id})")
            print(f"Candidate: {candidate_label} ({candidate.run_id})")
            print()
            print(format_comparison_table(comparison))

        if args.save:
            store = BenchmarkStore(args.db)
            store.save_run(baseline)
            store.save_run(candidate)
            print(f"Saved runs to {args.db}")
        return

    if args.command == "search-energy":
        candidates = [value.strip() for value in args.candidates.split(",") if value.strip()]
        if not candidates:
            parser.error("--candidates produced an empty scheduler list")

        baseline_settings = BenchmarkSettings(
            workload_name=args.workload,
            scheduler_name="linux_default",
            task_count=args.tasks,
            task_seconds=args.task_seconds,
            repetitions=args.repetitions,
            enable_perf_stat=args.perf_stat,
        )
        baseline = runner.run(baseline_settings)
        baseline_energy = _extract_collector_metric(baseline, "rapl", "package_energy_j")
        baseline_runtime = baseline.average_runtime_s

        records: list[dict[str, float | str]] = []
        successful_runs = []
        for sched_name in candidates:
            settings = BenchmarkSettings(
                workload_name=args.workload,
                scheduler_name="custom_sched_ext",
                task_count=args.tasks,
                task_seconds=args.task_seconds,
                repetitions=args.repetitions,
                sched_ext_scheduler=sched_name,
                enable_perf_stat=args.perf_stat,
            )
            try:
                candidate = runner.run(settings)
            except Exception as error:  # noqa: BLE001
                print(f"SKIP {sched_name}: {error}")
                continue

            successful_runs.append(candidate)
            energy = _extract_collector_metric(candidate, "rapl", "package_energy_j")
            runtime = candidate.average_runtime_s
            if baseline_energy is not None and energy is not None:
                energy_delta = energy - baseline_energy
                energy_delta_percent = 0.0 if baseline_energy == 0 else (energy_delta / baseline_energy) * 100
            else:
                energy_delta = float("nan")
                energy_delta_percent = float("nan")

            records.append(
                {
                    "scheduler": sched_name,
                    "runtime_s": runtime,
                    "energy_j": energy if energy is not None else float("nan"),
                    "energy_delta_j": energy_delta,
                    "energy_delta_percent": energy_delta_percent,
                }
            )

        print(f"Workload: {args.workload}")
        print(f"Baseline run: {baseline.run_id}")
        print(f"Baseline runtime_s: {baseline_runtime:.6g}")
        print(
            "Baseline energy_j: "
            + (f"{baseline_energy:.6g}" if baseline_energy is not None else "n/a")
        )
        print()
        print(_format_energy_search_table(records))

        lower_energy = [
            row
            for row in records
            if _is_finite(row["energy_delta_j"]) and float(row["energy_delta_j"]) < 0
        ]
        if lower_energy:
            best = min(lower_energy, key=lambda row: float(row["energy_delta_j"]))
            print()
            print(
                "Best lower-energy candidate: "
                f"{best['scheduler']} "
                f"({float(best['energy_delta_j']):.6g} J, {float(best['energy_delta_percent']):.6g}%)"
            )
        else:
            print()
            print("No lower-energy candidate found in this sweep.")

        if args.save:
            store = BenchmarkStore(args.db)
            store.save_run(baseline)
            for candidate in successful_runs:
                store.save_run(candidate)
            print(f"Saved runs to {args.db}")
        return

    if args.command == "median-board":
        candidates = [value.strip() for value in args.candidates.split(",") if value.strip()]
        if not candidates:
            parser.error("--candidates produced an empty scheduler list")

        progress_callback = None
        if args.progress:
            progress_callback = lambda message: print(message, file=sys.stderr, flush=True)

        leaderboard = run_median_leaderboard(
            runner=runner,
            workload_name=args.workload,
            task_count=args.tasks,
            task_seconds=args.task_seconds,
            repetitions=args.repetitions,
            trials=args.trials,
            candidates=candidates,
            enable_perf_stat=args.perf_stat,
            progress_callback=progress_callback,
        )
        if args.json:
            print(json.dumps(leaderboard, indent=2))
            return

        print(
            "Median leaderboard "
            f"(workload={args.workload}, tasks={args.tasks}, task_seconds={args.task_seconds}, "
            f"repetitions={args.repetitions}, trials={leaderboard['trials']})"
        )
        print()
        print(_format_median_board_table(leaderboard["rows"]))
        return

    if args.command == "results":
        store = BenchmarkStore(args.db)
        if args.run_id:
            payload = store.get_run_payload(args.run_id)
            if payload is None:
                parser.error(f"run_id not found: {args.run_id}")
            print(json.dumps(payload, indent=2))
            return

        rows = store.list_runs(
            limit=args.limit,
            scheduler_name=args.scheduler,
            workload_name=args.workload,
            from_time=args.from_time,
            to_time=args.to_time,
            sort_by=args.sort_by,
            sort_order=args.sort_order,
        )
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "run_id": row.run_id,
                            "created_at": row.created_at,
                            "workload_name": row.workload_name,
                            "scheduler_name": row.scheduler_name,
                            "task_count": row.task_count,
                            "task_seconds": row.task_seconds,
                            "repetitions": row.repetitions,
                            "average_runtime_s": row.average_runtime_s,
                        }
                        for row in rows
                    ],
                    indent=2,
                )
            )
            return

        print(_format_results_table(rows))
        return

    if args.command == "serve":
        try:
            from uvicorn import run as run_uvicorn
        except ImportError as error:
            parser.error(f"serve requires uvicorn to be installed: {error}")
        run_uvicorn(
            "energy_scheduler.api:app",
            host=args.host,
            port=args.port,
            reload=args.reload,
        )
        return

    settings = BenchmarkSettings(
        workload_name=args.workload,
        scheduler_name=args.scheduler,
        task_count=args.tasks,
        task_seconds=args.task_seconds,
        repetitions=args.repetitions,
        sched_ext_scheduler=args.sched_ext_scheduler,
        sched_ext_args=args.sched_ext_args,
        enable_perf_stat=args.perf_stat,
    )
    result = runner.run(settings)
    print(json.dumps(result.to_dict(), indent=2))

    if args.save:
        store = BenchmarkStore(args.db)
        store.save_run(result)
        print(f"Saved run to {args.db}")


def _format_results_table(rows: list[StoredRunSummary]) -> str:
    if not rows:
        return "No saved runs found."

    table_rows = [
        (
            "run_id",
            "created_at",
            "workload",
            "scheduler",
            "tasks",
            "task_s",
            "repetitions",
            "avg_runtime_s",
        ),
        *(
            (
                row.run_id,
                row.created_at,
                row.workload_name,
                row.scheduler_name,
                str(row.task_count),
                f"{row.task_seconds:.6g}",
                str(row.repetitions),
                "n/a"
                if row.average_runtime_s is None
                else f"{row.average_runtime_s:.6g}",
            )
            for row in rows
        ),
    ]
    widths = [max(len(row[column]) for row in table_rows) for column in range(len(table_rows[0]))]
    lines = []
    for index, row in enumerate(table_rows):
        lines.append("  ".join(value.ljust(widths[column]) for column, value in enumerate(row)))
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _extract_collector_metric(
    run: object,
    collector_name: str,
    metric_name: str,
) -> float | None:
    collector_readings = getattr(run, "collector_readings", ())
    for reading in collector_readings:
        if reading.collector_name != collector_name:
            continue
        value = reading.metrics.get(metric_name)
        if isinstance(value, (float, int)):
            return float(value)
    return None


def _format_energy_search_table(rows: list[dict[str, float | str]]) -> str:
    if not rows:
        return "No sched_ext candidates produced successful runs."

    table_rows = [
        ("scheduler", "runtime_s", "energy_j", "delta_j", "delta_%"),
        *(
            (
                str(row["scheduler"]),
                _format_numeric(row["runtime_s"]),
                _format_numeric(row["energy_j"]),
                _format_numeric(row["energy_delta_j"]),
                _format_numeric(row["energy_delta_percent"]),
            )
            for row in rows
        ),
    ]
    widths = [max(len(row[index]) for row in table_rows) for index in range(len(table_rows[0]))]
    lines: list[str] = []
    for index, row in enumerate(table_rows):
        lines.append("  ".join(value.ljust(widths[column]) for column, value in enumerate(row)))
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _format_median_board_table(rows: list[dict[str, object]]) -> str:
    if not rows:
        return "No median leaderboard rows available."

    table_rows = [
        (
            "label",
            "actual_name",
            "samples",
            "failed",
            "median_energy_j",
            "delta_j",
            "delta_%",
            "median_runtime_s",
        ),
        *(
            (
                str(row.get("label", "")),
                str(row.get("actual_name", "")),
                str(row.get("samples", "")),
                str(row.get("failed_trials", "")),
                _format_numeric(_safe_float(row.get("median_energy_j"))),
                _format_numeric(_safe_float(row.get("median_delta_j"))),
                _format_numeric(_safe_float(row.get("median_delta_percent"))),
                _format_numeric(_safe_float(row.get("median_runtime_s"))),
            )
            for row in rows
        ),
    ]
    widths = [max(len(row[index]) for row in table_rows) for index in range(len(table_rows[0]))]
    lines: list[str] = []
    for index, row in enumerate(table_rows):
        lines.append("  ".join(value.ljust(widths[column]) for column, value in enumerate(row)))
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _format_numeric(value: float | int | str) -> str:
    if isinstance(value, str):
        return value
    numeric = float(value)
    if not _is_finite(numeric):
        return "n/a"
    return f"{numeric:.6g}"


def _safe_float(value: object) -> float:
    if isinstance(value, (float, int)):
        return float(value)
    return float("nan")


def _is_finite(value: float | int) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))
