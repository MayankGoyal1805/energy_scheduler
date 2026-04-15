from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True, frozen=True)
class AppPaths:
    project_root: Path
    data_dir: Path
    database_path: Path

    @classmethod
    def default(cls) -> "AppPaths":
        project_root = Path.cwd()
        data_dir = project_root / "data"
        return cls(
            project_root=project_root,
            data_dir=data_dir,
            database_path=data_dir / "benchmark_runs.sqlite3",
        )


@dataclass(slots=True, frozen=True)
class BenchmarkSettings:
    workload_name: str
    scheduler_name: str
    task_count: int = 4
    task_seconds: float = 0.25
    repetitions: int = 1
    sched_ext_scheduler: str = "cake"
    sched_ext_args: str | None = None
    enable_perf_stat: bool = False
