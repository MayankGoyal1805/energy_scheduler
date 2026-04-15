# Energy Scheduler

## Python Environment

This project uses `uv` for Python package and environment management.

Project-level `uv` configuration lives in [uv.toml](/home/mayank/repos/energy_scheduler/uv.toml:1), which sets:

- a local cache directory at `.uv-cache`

That is important in this workspace because the default user cache location may not be writable.

### Common commands

```bash
uv venv
uv sync
uv run energy-scheduler workloads
uv run energy-scheduler doctor
uv run energy-scheduler run --workload cpu_bound
uv run energy-scheduler run --workload cpu_bound --perf-stat
uv run energy-scheduler compare --workload mixed --tasks 4
uv run energy-scheduler compare --workload mixed --tasks 4 --perf-stat
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed
uv run energy-scheduler results --limit 20
uv run energy-scheduler results --scheduler linux_default --workload mixed --json
uv run energy-scheduler results --from-time 2026-04-14T00:00:00 --to-time 2026-04-15T00:00:00
uv run energy-scheduler results --sort-by average_runtime_s --sort-order asc
uv run energy-scheduler results --run-id <run_id>
uv run energy-scheduler serve --host 127.0.0.1 --port 8000
```

### Fish shell note

The earlier `uv` issue was not caused by `fish`. The actual problem was the cache location. With the
project-local `uv.toml`, normal `uv` commands should work regardless of whether you are using `bash`
or `fish`.

## Current Backend

The backend skeleton is in place with:

- synthetic workloads
- lightweight application-style workloads
- a benchmark runner
- collector and scheduler interfaces
- SQLite storage
- FastAPI endpoints for workloads, doctor, run, compare, and results

See:

- [docs/setup.md](/home/mayank/repos/energy_scheduler/docs/setup.md:1)
- [docs/architecture.md](/home/mayank/repos/energy_scheduler/docs/architecture.md:1)
- [docs/workloads.md](/home/mayank/repos/energy_scheduler/docs/workloads.md:1)
- [docs/energy-collection.md](/home/mayank/repos/energy_scheduler/docs/energy-collection.md:1)
- [docs/performance-collection.md](/home/mayank/repos/energy_scheduler/docs/performance-collection.md:1)
- [docs/custom-scheduler.md](/home/mayank/repos/energy_scheduler/docs/custom-scheduler.md:1)
- [docs/comparison-workflow.md](/home/mayank/repos/energy_scheduler/docs/comparison-workflow.md:1)
- [docs/api.md](/home/mayank/repos/energy_scheduler/docs/api.md:1)
- [docs/cli-reference.md](/home/mayank/repos/energy_scheduler/docs/cli-reference.md:1)
- [docs/storage-and-results.md](/home/mayank/repos/energy_scheduler/docs/storage-and-results.md:1)
- [docs/backend-runbook.md](/home/mayank/repos/energy_scheduler/docs/backend-runbook.md:1)
- [docs/sched-ext.md](/home/mayank/repos/energy_scheduler/docs/sched-ext.md:1)
