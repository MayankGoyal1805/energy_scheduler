# Backend API

## Overview

The project now exposes a FastAPI layer over the existing benchmark backend.

Start the server:

```bash
uv run energy-scheduler serve --host 127.0.0.1 --port 8000
```

Open interactive docs:

```text
http://127.0.0.1:8000/docs
```

## Endpoints

### Dashboard UI

- `GET /`

Returns the local dashboard HTML.

- `GET /assets/*`

Serves dashboard static assets (JS/CSS).

### Health

- `GET /health`

Returns service health status.

### Workloads

- `GET /workloads`

Returns all available workload names.

### Doctor

- `GET /doctor`

Returns environment checks currently used by the CLI doctor command.

### Run Benchmark

- `POST /run`

Request body:

```json
{
  "workload": "cpu_bound",
  "scheduler": "linux_default",
  "tasks": 4,
  "task_seconds": 0.25,
  "repetitions": 1,
  "sched_ext_scheduler": "cake",
  "sched_ext_args": null,
  "perf_stat": false,
  "save": false,
  "db_path": null
}
```

Response includes the full benchmark payload plus a `saved` flag.

### Compare Benchmarks

- `POST /compare`

Request body:

```json
{
  "workload": "mixed",
  "tasks": 4,
  "task_seconds": 0.25,
  "repetitions": 1,
  "candidate_scheduler": "custom_simulated",
  "sched_ext_scheduler": "cake",
  "sched_ext_args": null,
  "perf_stat": false,
  "save": false,
  "db_path": null
}
```

Response includes:

- comparison metrics
- baseline full run payload
- candidate full run payload
- `saved` flag

### Median Leaderboard

- `POST /median-board`

Request body:

```json
{
  "workload": "mixed_realistic",
  "tasks": 8,
  "task_seconds": 0.5,
  "repetitions": 3,
  "trials": 5,
  "candidates": "cake,lavd,flash,bpfland,cosmos,p2dq,tickless,rustland,rusty,beerland,pandemonium",
  "perf_stat": false
}
```

Response includes one row per scheduler with:

- median energy in joules
- median runtime
- median delta vs baseline
- sample count and failed-trial count

### List Saved Results

- `GET /results?limit=20&scheduler=linux_default&workload=mixed&from_time=2026-04-14T00:00:00&to_time=2026-04-15T00:00:00&sort_by=average_runtime_s&sort_order=asc`

Returns saved run summaries.

Supported sorting fields:

- `created_at`
- `workload_name`
- `scheduler_name`
- `task_count`
- `task_seconds`
- `repetitions`
- `average_runtime_s`

### Get Saved Result

- `GET /results/{run_id}`

Returns full saved payload for one run id.

### Async Run Job

- `POST /jobs/run`

Same request body as `POST /run`, but returns immediately with a job id.

### Async Compare Job

- `POST /jobs/compare`

Same request body as `POST /compare`, but returns immediately with a job id.

### Async Median Leaderboard Job

- `POST /jobs/median-board`

Same request body as `POST /median-board`, but returns immediately with a job id.

### Job Status

- `GET /jobs/{job_id}`

Returns queued/running/completed/failed status and result payload when complete.

### Job Logs (Live Progress)

- `GET /jobs/{job_id}/logs?since=0&limit=200`

Returns incremental timestamped log lines for long-running jobs.

Response fields:

- `from_index`
- `to_index`
- `logs`

The UI should poll this endpoint and pass `since=<previous to_index>` to append only new lines.

## Notes

- API endpoints call the same runner, compare, doctor, and storage logic as the CLI.
- `perf_stat` uses `perf stat` during the benchmark window and returns parsed perf counters when available.
- If you use `custom_sched_ext` through the API, scheduler switching still applies system-wide during execution.
