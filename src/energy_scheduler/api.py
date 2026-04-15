from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Callable
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from energy_scheduler.compare import compare_runs
from energy_scheduler.config import AppPaths, BenchmarkSettings
from energy_scheduler.doctor import run_doctor
from energy_scheduler.leaderboard import run_median_leaderboard
from energy_scheduler.runner import BenchmarkRunner
from energy_scheduler.storage import BenchmarkStore


app = FastAPI(
    title="Energy Scheduler API",
    description="HTTP API for running and comparing scheduler benchmarks.",
    version="0.1.0",
)

_EXECUTOR = ThreadPoolExecutor(max_workers=2)
_JOBS: dict[str, dict[str, object]] = {}
_JOBS_LOCK = Lock()
_WEB_DIR = Path(__file__).resolve().parent / "web"
_DEFAULT_SCHED_EXT_CANDIDATES = [
    "beerland",
    "bpfland",
    "cake",
    "cosmos",
    "flash",
    "lavd",
    "pandemonium",
    "p2dq",
    "tickless",
    "rustland",
    "rusty",
]

if _WEB_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(_WEB_DIR)), name="assets")


class ResultSummary(BaseModel):
    run_id: str
    created_at: str
    workload_name: str
    scheduler_name: str
    task_count: int
    task_seconds: float
    repetitions: int
    average_runtime_s: float | None


class JobStatus(BaseModel):
    job_id: str
    kind: str
    status: str
    submitted_at: str
    started_at: str | None
    finished_at: str | None
    error: str | None
    result: dict[str, object] | None
    logs: list[str] = Field(default_factory=list)


class JobLogsResponse(BaseModel):
    job_id: str
    status: str
    from_index: int
    to_index: int
    logs: list[str]


class RunRequest(BaseModel):
    workload: str = Field(default="cpu_bound")
    scheduler: str = Field(default="linux_default")
    tasks: int = Field(default=4, ge=1)
    task_seconds: float = Field(default=0.25, gt=0.0)
    repetitions: int = Field(default=1, ge=1)
    sched_ext_scheduler: str = Field(default="cake")
    sched_ext_args: str | None = Field(default=None)
    perf_stat: bool = Field(default=False)
    save: bool = Field(default=False)
    db_path: str | None = None


class CompareRequest(BaseModel):
    workload: str = Field(default="cpu_bound")
    tasks: int = Field(default=4, ge=1)
    task_seconds: float = Field(default=0.25, gt=0.0)
    repetitions: int = Field(default=1, ge=1)
    candidate_scheduler: str = Field(default="custom_simulated")
    sched_ext_scheduler: str = Field(default="cake")
    sched_ext_args: str | None = Field(default=None)
    perf_stat: bool = Field(default=False)
    save: bool = Field(default=False)
    db_path: str | None = None


class MedianBoardRequest(BaseModel):
    workload: str = Field(default="cpu_bound")
    tasks: int = Field(default=4, ge=1)
    task_seconds: float = Field(default=0.25, gt=0.0)
    repetitions: int = Field(default=1, ge=1)
    trials: int = Field(default=5, ge=1)
    candidates: str = Field(
        default="cake,lavd,flash,bpfland,cosmos,p2dq,tickless,rustland,rusty,beerland,pandemonium"
    )
    perf_stat: bool = Field(default=False)
    save: bool = Field(default=False)
    db_path: str | None = None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _run_payload(request: RunRequest) -> dict[str, object]:
    runner = BenchmarkRunner()
    settings = BenchmarkSettings(
        workload_name=request.workload,
        scheduler_name=request.scheduler,
        task_count=request.tasks,
        task_seconds=request.task_seconds,
        repetitions=request.repetitions,
        sched_ext_scheduler=request.sched_ext_scheduler,
        sched_ext_args=request.sched_ext_args,
        enable_perf_stat=request.perf_stat,
    )
    result = runner.run(settings)
    payload = result.to_dict()
    if request.save:
        store = _store(request.db_path)
        store.save_run(result)
        payload["saved"] = True
    else:
        payload["saved"] = False
    return payload


def _compare_payload(request: CompareRequest) -> dict[str, object]:
    runner = BenchmarkRunner()
    baseline_settings = BenchmarkSettings(
        workload_name=request.workload,
        scheduler_name="linux_default",
        task_count=request.tasks,
        task_seconds=request.task_seconds,
        repetitions=request.repetitions,
        enable_perf_stat=request.perf_stat,
    )
    candidate_settings = BenchmarkSettings(
        workload_name=request.workload,
        scheduler_name=request.candidate_scheduler,
        task_count=request.tasks,
        task_seconds=request.task_seconds,
        repetitions=request.repetitions,
        sched_ext_scheduler=request.sched_ext_scheduler,
        sched_ext_args=request.sched_ext_args,
        enable_perf_stat=request.perf_stat,
    )

    baseline = runner.run(baseline_settings)
    candidate = runner.run(candidate_settings)
    payload = compare_runs(baseline, candidate).to_dict()
    payload["baseline_run"] = baseline.to_dict()
    payload["candidate_run"] = candidate.to_dict()

    if request.save:
        store = _store(request.db_path)
        store.save_run(baseline)
        store.save_run(candidate)
        payload["saved"] = True
    else:
        payload["saved"] = False
    return payload


def _median_board_payload(
    request: MedianBoardRequest,
    progress_callback: Callable[[str], None] | None = None,
) -> dict[str, object]:
    runner = BenchmarkRunner()
    candidates = [value.strip() for value in request.candidates.split(",") if value.strip()]
    if not candidates:
        raise ValueError("candidates list is empty")

    result = run_median_leaderboard(
        runner=runner,
        workload_name=request.workload,
        task_count=request.tasks,
        task_seconds=request.task_seconds,
        repetitions=request.repetitions,
        trials=request.trials,
        candidates=candidates,
        enable_perf_stat=request.perf_stat,
        progress_callback=progress_callback,
    )
    
    if request.save:
        store = _store(request.db_path)
        store.save_median_run(
            workload_name=request.workload,
            tasks=request.tasks,
            task_seconds=request.task_seconds,
            repetitions=request.repetitions,
            trials=request.trials,
            candidates=candidates,
            perf_stat=request.perf_stat,
            result_json=result,
        )
        result["saved"] = True
    else:
        result["saved"] = False
    
    return result


def _submit_job(
    kind: str,
    fn: Callable[[Callable[[str], None]], dict[str, object]],
) -> JobStatus:
    job_id = str(uuid4())
    with _JOBS_LOCK:
        _JOBS[job_id] = {
            "job_id": job_id,
            "kind": kind,
            "status": "queued",
            "submitted_at": _now_iso(),
            "started_at": None,
            "finished_at": None,
            "error": None,
            "result": None,
            "logs": [],
        }

    def _wrapped() -> None:
        def _progress(message: str) -> None:
            _append_job_log(job_id, message)

        with _JOBS_LOCK:
            _JOBS[job_id]["status"] = "running"
            _JOBS[job_id]["started_at"] = _now_iso()
        _progress(f"job {job_id} started ({kind})")
        try:
            result = fn(_progress)
            with _JOBS_LOCK:
                _JOBS[job_id]["status"] = "completed"
                _JOBS[job_id]["result"] = result
                _JOBS[job_id]["finished_at"] = _now_iso()
            _progress(f"job {job_id} completed")
        except Exception as error:  # noqa: BLE001
            with _JOBS_LOCK:
                _JOBS[job_id]["status"] = "failed"
                _JOBS[job_id]["error"] = str(error)
                _JOBS[job_id]["finished_at"] = _now_iso()
            _progress(f"job {job_id} failed: {error}")

    _EXECUTOR.submit(_wrapped)
    with _JOBS_LOCK:
        return JobStatus(**_JOBS[job_id])


def _store(db_path: str | None) -> BenchmarkStore:
    resolved = Path(db_path) if db_path else AppPaths.default().database_path
    return BenchmarkStore(resolved)


def _append_job_log(job_id: str, message: str) -> None:
    timestamped = f"[{_now_iso()}] {message}"
    with _JOBS_LOCK:
        payload = _JOBS.get(job_id)
        if payload is None:
            return
        logs = payload.get("logs")
        if not isinstance(logs, list):
            payload["logs"] = [timestamped]
            return
        logs.append(timestamped)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/", include_in_schema=False)
def web_index() -> FileResponse:
    index_path = _WEB_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="UI not found")
    return FileResponse(index_path)


@app.get("/workloads")
def workloads() -> list[str]:
    return BenchmarkRunner().available_workloads()


@app.get("/sched-ext-candidates")
def sched_ext_candidates() -> list[str]:
    return _DEFAULT_SCHED_EXT_CANDIDATES


@app.get("/doctor")
def doctor() -> dict[str, object]:
    return run_doctor().to_dict()


@app.post("/run")
def run_benchmark(request: RunRequest) -> dict[str, object]:
    return _run_payload(request)


@app.post("/compare")
def compare_benchmarks(request: CompareRequest) -> dict[str, object]:
    return _compare_payload(request)


@app.post("/median-board")
def median_board(request: MedianBoardRequest) -> dict[str, object]:
    return _median_board_payload(request)


@app.post("/median-runs/query")
def median_runs_query(request: MedianBoardRequest) -> dict:
    store = _store(request.db_path)
    
    candidates = [value.strip() for value in request.candidates.split(",") if value.strip()]
    result = store.query_median_run(
        workload_name=request.workload,
        tasks=request.tasks,
        task_seconds=request.task_seconds,
        repetitions=request.repetitions,
        trials=request.trials,
        candidates=candidates,
        perf_stat=request.perf_stat,
    )
    if not result:
        return {}
    return result


@app.post("/jobs/run", response_model=JobStatus)
def submit_run_job(request: RunRequest) -> JobStatus:
    return _submit_job("run", lambda _progress: _run_payload(request))


@app.post("/jobs/compare", response_model=JobStatus)
def submit_compare_job(request: CompareRequest) -> JobStatus:
    return _submit_job("compare", lambda _progress: _compare_payload(request))


@app.post("/jobs/median-board", response_model=JobStatus)
def submit_median_board_job(request: MedianBoardRequest) -> JobStatus:
    return _submit_job("median-board", lambda progress: _median_board_payload(request, progress))


@app.get("/jobs/{job_id}", response_model=JobStatus)
def get_job(job_id: str) -> JobStatus:
    with _JOBS_LOCK:
        payload = _JOBS.get(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")
    return JobStatus(**payload)


@app.get("/jobs/{job_id}/logs", response_model=JobLogsResponse)
def get_job_logs(
    job_id: str,
    since: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=2000),
) -> JobLogsResponse:
    with _JOBS_LOCK:
        payload = _JOBS.get(job_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"job not found: {job_id}")

    status = str(payload.get("status", "unknown"))
    logs = payload.get("logs")
    if not isinstance(logs, list):
        logs = []

    start = min(since, len(logs))
    end = min(start + limit, len(logs))
    sliced = [str(line) for line in logs[start:end]]
    return JobLogsResponse(
        job_id=job_id,
        status=status,
        from_index=start,
        to_index=end,
        logs=sliced,
    )


@app.get("/results")
def list_results(
    limit: int = Query(default=20, ge=1),
    scheduler: str | None = None,
    workload: str | None = None,
    from_time: str | None = None,
    to_time: str | None = None,
    sort_by: str = Query(default="created_at"),
    sort_order: str = Query(default="desc"),
    db_path: str | None = None,
) -> list[ResultSummary]:
    rows = _store(db_path).list_runs(
        limit=limit,
        scheduler_name=scheduler,
        workload_name=workload,
        from_time=from_time,
        to_time=to_time,
        sort_by=sort_by,
        sort_order=sort_order,
    )
    return [
        ResultSummary(
            run_id=row.run_id,
            created_at=row.created_at,
            workload_name=row.workload_name,
            scheduler_name=row.scheduler_name,
            task_count=row.task_count,
            task_seconds=row.task_seconds,
            repetitions=row.repetitions,
            average_runtime_s=row.average_runtime_s,
        )
        for row in rows
    ]


@app.get("/results/{run_id}")
def get_result(run_id: str, db_path: str | None = None) -> dict[str, object]:
    payload = _store(db_path).get_run_payload(run_id)
    if payload is None:
        raise HTTPException(status_code=404, detail=f"run_id not found: {run_id}")
    return payload