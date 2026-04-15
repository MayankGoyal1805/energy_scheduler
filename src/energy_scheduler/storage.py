from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import sqlite3
import uuid
from pathlib import Path
from typing import Any

from energy_scheduler.models import BenchmarkRun


@dataclass(slots=True, frozen=True)
class StoredRunSummary:
    run_id: str
    created_at: str
    workload_name: str
    scheduler_name: str
    task_count: int
    task_seconds: float
    repetitions: int
    average_runtime_s: float | None


class BenchmarkStore:
    def __init__(self, database_path: Path) -> None:
        self._database_path = database_path
        self._database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _initialize(self) -> None:
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS benchmark_runs (
                    run_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    workload_name TEXT NOT NULL,
                    scheduler_name TEXT NOT NULL,
                    task_count INTEGER NOT NULL,
                    task_seconds REAL NOT NULL,
                    repetitions INTEGER NOT NULL,
                    summary_json TEXT NOT NULL
                )
                """
            )
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(benchmark_runs)").fetchall()
            }
            if "created_at" not in columns:
                connection.execute(
                    "ALTER TABLE benchmark_runs ADD COLUMN created_at TEXT"
                )
                connection.execute(
                    "UPDATE benchmark_runs SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"
                )
                
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS median_runs (
                    id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    workload_name TEXT NOT NULL,
                    tasks INTEGER NOT NULL,
                    task_seconds REAL NOT NULL,
                    repetitions INTEGER NOT NULL,
                    trials INTEGER NOT NULL,
                    candidates TEXT NOT NULL,
                    perf_stat INTEGER NOT NULL,
                    result_json TEXT NOT NULL
                )
                """
            )
            connection.commit()

    def list_runs(
        self,
        *,
        limit: int = 20,
        scheduler_name: str | None = None,
        workload_name: str | None = None,
        from_time: str | None = None,
        to_time: str | None = None,
        sort_by: str = "created_at",
        sort_order: str = "desc",
    ) -> list[StoredRunSummary]:
        query = """
            SELECT
                run_id,
                created_at,
                workload_name,
                scheduler_name,
                task_count,
                task_seconds,
                repetitions,
                summary_json
            FROM benchmark_runs
        """
        where_clauses: list[str] = []
        params: list[Any] = []

        if scheduler_name:
            where_clauses.append("scheduler_name = ?")
            params.append(scheduler_name)
        if workload_name:
            where_clauses.append("workload_name = ?")
            params.append(workload_name)
        normalized_from = _normalize_timestamp(from_time)
        if normalized_from:
            where_clauses.append("created_at >= ?")
            params.append(normalized_from)
        normalized_to = _normalize_timestamp(to_time)
        if normalized_to:
            where_clauses.append("created_at <= ?")
            params.append(normalized_to)

        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)

        order = "ASC" if sort_order.lower() == "asc" else "DESC"
        sql_sort_columns = {
            "created_at": "created_at",
            "workload_name": "workload_name",
            "scheduler_name": "scheduler_name",
            "task_count": "task_count",
            "task_seconds": "task_seconds",
            "repetitions": "repetitions",
        }
        sort_key = sort_by if sort_by in sql_sort_columns else "created_at"
        if sort_key == "average_runtime_s":
            query += " ORDER BY rowid DESC"
        else:
            query += f" ORDER BY {sql_sort_columns[sort_key]} {order}"

        effective_limit = max(limit, 1)
        if sort_key != "average_runtime_s":
            query += " LIMIT ?"
            params.append(effective_limit)

        with sqlite3.connect(self._database_path) as connection:
            rows = connection.execute(query, tuple(params)).fetchall()

        summaries: list[StoredRunSummary] = []
        for row in rows:
            payload = json.loads(row[7])
            summary = payload.get("summary", {})
            average_runtime_s = summary.get("average_runtime_s")
            summaries.append(
                StoredRunSummary(
                    run_id=row[0],
                    created_at=row[1],
                    workload_name=row[2],
                    scheduler_name=row[3],
                    task_count=row[4],
                    task_seconds=row[5],
                    repetitions=row[6],
                    average_runtime_s=average_runtime_s
                    if isinstance(average_runtime_s, float)
                    else None,
                )
            )

        if sort_key == "average_runtime_s":
            present = [row for row in summaries if row.average_runtime_s is not None]
            missing = [row for row in summaries if row.average_runtime_s is None]
            present.sort(
                key=lambda row: row.average_runtime_s or 0.0,
                reverse=order == "DESC",
            )
            summaries = [*present, *missing]
            summaries = summaries[:effective_limit]

        return summaries

    def get_run_payload(self, run_id: str) -> dict[str, Any] | None:
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                "SELECT summary_json FROM benchmark_runs WHERE run_id = ?",
                (run_id,),
            ).fetchone()

        if row is None:
            return None
        return json.loads(row[0])

    def save_run(self, benchmark_run: BenchmarkRun) -> None:
        payload = benchmark_run.to_dict()
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO benchmark_runs (
                    run_id,
                    created_at,
                    workload_name,
                    scheduler_name,
                    task_count,
                    task_seconds,
                    repetitions,
                    summary_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    benchmark_run.run_id,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    benchmark_run.workload_name,
                    benchmark_run.scheduler_name,
                    benchmark_run.task_count,
                    benchmark_run.task_seconds,
                    benchmark_run.repetitions,
                    json.dumps(payload),
                ),
            )
            connection.commit()

    def query_median_run(
        self,
        workload_name: str,
        tasks: int,
        task_seconds: float,
        repetitions: int,
        trials: int,
        candidates: list[str],
        perf_stat: bool,
    ) -> dict | None:
        sorted_candidates = ",".join(sorted(candidates))
        with sqlite3.connect(self._database_path) as connection:
            row = connection.execute(
                """
                SELECT result_json FROM median_runs
                WHERE workload_name = ?
                  AND tasks = ?
                  AND task_seconds = ?
                  AND repetitions = ?
                  AND trials = ?
                  AND candidates = ?
                  AND perf_stat = ?
                """,
                (
                    workload_name,
                    tasks,
                    task_seconds,
                    repetitions,
                    trials,
                    sorted_candidates,
                    1 if perf_stat else 0,
                ),
            ).fetchone()

        if row is None:
            return None
        return json.loads(row[0])

    def save_median_run(
        self,
        workload_name: str,
        tasks: int,
        task_seconds: float,
        repetitions: int,
        trials: int,
        candidates: list[str],
        perf_stat: bool,
        result_json: dict,
    ) -> str:
        run_id = str(uuid.uuid4())
        sorted_candidates = ",".join(sorted(candidates))
        payload_str = json.dumps(result_json)
        with sqlite3.connect(self._database_path) as connection:
            connection.execute(
                """
                INSERT INTO median_runs (
                    id,
                    created_at,
                    workload_name,
                    tasks,
                    task_seconds,
                    repetitions,
                    trials,
                    candidates,
                    perf_stat,
                    result_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    workload_name,
                    tasks,
                    task_seconds,
                    repetitions,
                    trials,
                    sorted_candidates,
                    1 if perf_stat else 0,
                    payload_str,
                ),
            )
            connection.commit()
        return run_id


def _normalize_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    normalized = value.strip().replace("T", " ")
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    return normalized
