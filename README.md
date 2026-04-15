
# Energy Scheduler

**Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment**

This project benchmarks and compares Linux's default scheduler against both a simulated energy-aware scheduler and real kernel sched_ext schedulers, with a focus on energy and performance metrics. It provides a reproducible backend, a modern dashboard UI, and a strict caching system to avoid redundant runs.

---

## Project Overview

- **Backend:** Python (FastAPI, SQLite, uv)
- **Frontend:** Modern dashboard UI (static HTML/JS/CSS, Plotly.js)
- **Workloads:** Synthetic and lightweight application-style
- **Schedulers:**
	- `linux_default` (real Linux)
	- `custom_simulated` (Python model, not kernel)
	- `custom_sched_ext` (real kernel switching via sched_ext, e.g. cake/lavd)
- **Metrics:** Runtime, context switches, RAPL energy (when available), perf counters
- **Caching:** Strict backend caching—identical parameter runs are never repeated

---

## Quickstart

```bash
uv venv
uv sync
uv run energy-scheduler doctor
uv run energy-scheduler workloads
uv run energy-scheduler run --workload cpu_bound
uv run energy-scheduler compare --workload mixed --tasks 4
uv run energy-scheduler serve --host 127.0.0.1 --port 8000
```

See [docs/cli-reference.md](docs/cli-reference.md) for all commands and options.

---

## Dashboard UI

- Modern, responsive dashboard for local benchmarking and comparison
- Only real schedulers (no custom/simulated) are shown as candidates in the UI
- Comparison section uses only relevant charts (no long tables)
- Per-workload blocks show compact, color-coded tables and charts
- All results are cached—no redundant runs

---

## Backend Features

- Synthetic and application-style workloads
- Benchmark runner with collector and scheduler interfaces
- SQLite storage for all runs and comparisons
- FastAPI backend with endpoints for workloads, doctor, run, compare, results, leaderboard, and async jobs
- Strict parameter-based caching (see [docs/storage-and-results.md](docs/storage-and-results.md))

---

## Schedulers: What’s Real and What’s Simulated

- `linux_default`: Real Linux scheduler (CFS/EEVDF)
- `custom_simulated`: Python simulation of our energy-aware algorithm (model only, not kernel)
- `custom_sched_ext`: Real kernel switching via sched_ext (e.g. cake, lavd, etc.)
	- **Note:** None of the installed sched_ext schedulers are our custom algorithm; they are used for real kernel experiments only

**Do not claim:**
- That any third-party sched_ext scheduler is our algorithm
- That simulated energy units are real joules
- That per-process energy is measured (RAPL is package-level only)

---

## Energy Measurement Status

- RAPL collector reads `/sys/class/powercap/intel-rapl/*/energy_uj` for package energy
- If permission denied, see [docs/ops-checklist.md](docs/ops-checklist.md) for host-side fixes
- All energy claims are only valid if RAPL is readable

---

## Documentation

- [docs/setup.md](docs/setup.md): Python/env setup, uv config
- [docs/architecture.md](docs/architecture.md): Backend structure and design
- [docs/workloads.md](docs/workloads.md): Workload types and rationale
- [docs/energy-collection.md](docs/energy-collection.md): RAPL and energy metrics
- [docs/performance-collection.md](docs/performance-collection.md): Perf/statistics collection
- [docs/custom-scheduler.md](docs/custom-scheduler.md): Simulated scheduler model
- [docs/comparison-workflow.md](docs/comparison-workflow.md): Comparison and leaderboard logic
- [docs/api.md](docs/api.md): FastAPI endpoints
- [docs/cli-reference.md](docs/cli-reference.md): CLI usage and options
- [docs/storage-and-results.md](docs/storage-and-results.md): Storage, caching, and results model
- [docs/backend-runbook.md](docs/backend-runbook.md): End-to-end backend operations
- [docs/sched-ext.md](docs/sched-ext.md): Real sched_ext scheduler integration
- [docs/ops-checklist.md](docs/ops-checklist.md): Operations checklist, RAPL fixes
- [docs/scheduler-energy-analysis.md](docs/scheduler-energy-analysis.md): Scheduler comparison and leaderboard analysis

---

## Reproducibility

- For stable results, set CPU governor to `performance` and minimize background load
- See [docs/ops-checklist.md](docs/ops-checklist.md) for reproducibility tips

---

## Status

- Backend: Complete (all endpoints, caching, collectors, sched_ext switching)
- UI: Complete (modern dashboard, strict candidate logic, chart-only comparison)
- RAPL: Permission fix may be required for real energy measurement

---
