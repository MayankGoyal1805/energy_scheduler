# Energy Scheduler Handoff

## Project Title

Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment

## Current Goal

Build a local benchmarking system that compares Linux's default scheduler against:

- a simulated version of our energy-aware dynamic quantum scheduler
- a real `sched_ext` scheduler path for actual Linux scheduler switching

The backend is the priority. The local web UI comes later and should consume the same runner,
comparison, and storage logic already built here.

## Current Status

This repo now has a working Python backend managed by `uv`.

Implemented:

- Python package skeleton under `src/energy_scheduler`
- CLI entrypoint: `uv run energy-scheduler ...`
- synthetic workloads
- lightweight application-style workloads
- benchmark runner
- SQLite run storage
- runtime/system/RAPL/performance collectors
- Linux default scheduler adapter
- Python `custom_simulated` scheduler
- real `custom_sched_ext` adapter using `scxctl`
- `doctor` command for environment checks
- `compare` command for baseline vs candidate summaries
- `results` command for listing and inspecting saved runs
- FastAPI backend API with run/compare/results/doctor/workloads endpoints
- FastAPI backend API with async jobs (`/jobs/run`, `/jobs/compare`, `/jobs/{job_id}`)
- optional `perf_stat` collector integrated into run/compare
- results query depth expanded (date range + sort)
- documentation under `docs/`

## Important Commands

List workloads:

```bash
uv run energy-scheduler workloads
```

Run a workload under default Linux scheduling:

```bash
uv run energy-scheduler run --scheduler linux_default --workload cpu_bound --tasks 2 --task-seconds 0.05
```

Run our simulated scheduler:

```bash
uv run energy-scheduler run --scheduler custom_simulated --workload mixed --tasks 4 --task-seconds 0.05
```

Run a real sched_ext scheduler:

```bash
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler lavd --workload cpu_bound --tasks 1 --task-seconds 0.02
```

Compare default Linux vs simulated scheduler:

```bash
uv run energy-scheduler compare --workload mixed --tasks 4 --task-seconds 0.05
```

Compare default Linux vs real sched_ext scheduler:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler lavd --workload cpu_bound --tasks 1 --task-seconds 0.02
```

Check environment:

```bash
uv run energy-scheduler doctor
```

Save a run or comparison:

```bash
uv run energy-scheduler run --workload mixed --save
uv run energy-scheduler compare --workload mixed --save
```

List saved runs and inspect a specific run:

```bash
uv run energy-scheduler results --limit 20
uv run energy-scheduler results --scheduler linux_default --workload mixed
uv run energy-scheduler results --run-id <run_id>
```

## Implemented Workloads

Synthetic workloads:

- `cpu_bound`
- `interactive_short`
- `mixed`
- `bursty_periodic`

Application-style workloads:

- `compression`
- `file_scan`
- `local_request_burst`
- `mixed_realistic`

Notes:

- Synthetic workloads are good for clean scheduler metrics such as waiting time and turnaround time.
- Application-style workloads are still lightweight and automated, but closer to real machine behavior.
- `local_request_burst` and `mixed_realistic` bind a temporary localhost server socket.
- In restricted sandboxes, localhost socket creation may need extra permission; on a normal machine it should work.

## Implemented Collectors

Current collectors:

- `runtime`
- `system_info`
- `rapl`
- `child_process_usage`
- `perf_info`
- `perf_stat` (optional)

RAPL collector:

- reads `/sys/class/powercap/intel-rapl/**/energy_uj`
- reports energy in microjoules/joules when readable
- handles counter wraparound using `max_energy_range_uj`
- returns an unavailable status instead of crashing when permission is denied

Process usage collector:

- uses `resource.getrusage(resource.RUSAGE_CHILDREN)`
- reports child CPU time, page faults, voluntary context switches, and involuntary context switches

`perf_info` collector:

- records whether `perf` exists
- records `perf --version`
- records `/proc/sys/kernel/perf_event_paranoid`

Current limitation:

- `perf_stat` currently attaches to the benchmark process window; a dedicated worker wrapper mode can further tighten process-tree isolation.

## Implemented Scheduler Modes

### `linux_default`

Real workload execution under the currently active Linux scheduler.

### `custom_simulated`

Python simulation of our proposed energy-aware dynamic quantum scheduler.

Important:

- this is not a real kernel scheduler
- it does not change Linux scheduling
- energy values are relative model units, not joules
- it emits `schedule_events` for future timeline visualization

Current formula shape:

```text
quantum = base_quantum * priority_factor * behavior_factor / energy_factor
```

Inputs:

- task priority
- CPU/sleep phase behavior
- estimated CPU intensity as an energy proxy

### `custom_sched_ext`

Real scheduler switching through `scxctl`.

Current behavior:

- starts an installed sched_ext scheduler before the workload
- runs the workload for real
- stops the sched_ext scheduler in cleanup
- records `scxctl start` and `scxctl stop` return metadata

Default sched_ext scheduler:

```text
lavd
```

Other installed schedulers reported by `scxctl list`:

```text
beerland, bpfland, cake, cosmos, flash, lavd, pandemonium, p2dq, tickless, rustland, rusty
```

Important:

- `lavd` is not our energy-aware dynamic quantum scheduler.
- `lavd` is currently used to prove that real sched_ext switching works.
- We have not implemented our own BPF sched_ext scheduler yet.

## Verified Environment

Kernel:

```text
6.19.11-1-cachyos
```

Detected:

- `/sys/kernel/sched_ext` exists
- `scxctl` exists
- `bpftool` exists
- `perf` exists
- `sched_ext` state returns to `disabled` after test runs
- `scxctl get` reports no scheduler running after cleanup

Verified real sched_ext run:

```bash
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler lavd --workload cpu_bound --tasks 1 --task-seconds 0.02
```

Verified real scheduler comparison:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler lavd --workload cpu_bound --tasks 1 --task-seconds 0.02
```

Current RAPL state:

- RAPL paths exist
- reading `energy_uj` currently returns permission denied in this environment
- therefore no real joule comparison has been proven yet

## What Is True Right Now

- We can run real workloads under Linux default scheduling.
- We can run simulated workloads under our proposed dynamic-quantum policy.
- We can switch the real Linux scheduler to an installed sched_ext scheduler such as `lavd`.
- We can compare default Linux vs simulated custom policy.
- We can compare default Linux vs real installed sched_ext scheduler.
- We cannot yet claim energy savings because RAPL is not readable.
- We cannot yet claim `lavd` is our scheduler.
- We have not yet implemented our own sched_ext BPF scheduler.

## What Not To Claim Yet

Do not claim:

- that `lavd` is our energy-aware scheduler
- that real energy consumption is lower
- that `custom_simulated` is a real kernel scheduler
- that the project has real per-process energy measurement

Correct framing:

- `custom_simulated` models our algorithm.
- `custom_sched_ext` proves real scheduler switching works.
- RAPL will provide real energy data after permissions are fixed.
- A custom BPF sched_ext scheduler is still future work.

## Key Files

CLI:

- `src/energy_scheduler/cli.py`

Runner:

- `src/energy_scheduler/runner.py`

Models:

- `src/energy_scheduler/models.py`

Comparison:

- `src/energy_scheduler/compare.py`

Doctor:

- `src/energy_scheduler/doctor.py`

Storage:

- `src/energy_scheduler/storage.py`

Collectors:

- `src/energy_scheduler/collectors/rapl.py`
- `src/energy_scheduler/collectors/process_usage.py`
- `src/energy_scheduler/collectors/perf_info.py`
- `src/energy_scheduler/collectors/runtime.py`

Schedulers:

- `src/energy_scheduler/schedulers/default.py`
- `src/energy_scheduler/schedulers/simulated.py`
- `src/energy_scheduler/schedulers/sched_ext.py`

Workloads:

- `src/energy_scheduler/workloads/synthetic.py`
- `src/energy_scheduler/workloads/application.py`

Docs:

- `docs/setup.md`
- `docs/architecture.md`
- `docs/workloads.md`
- `docs/energy-collection.md`
- `docs/performance-collection.md`
- `docs/custom-scheduler.md`
- `docs/comparison-workflow.md`
- `docs/api.md`
- `docs/cli-reference.md`
- `docs/storage-and-results.md`
- `docs/backend-runbook.md`
- `docs/sched-ext.md`

## Next Tasks

### 1. Fix RAPL permissions

Goal:

- make `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` readable
- get real joule measurements in benchmark output

Why:

- without this, we cannot prove energy reduction

Suggested check:

```bash
ls -l /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
uv run energy-scheduler doctor
```

Possible fix:

- add a udev rule or group permission on the real machine
- user said sudo does not work inside this environment, so they may need to install/configure manually

### 2. Run longer baseline experiments

Use longer runs after RAPL works:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler lavd --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3
```

Purpose:

- compare default Linux vs real sched_ext under more meaningful workloads
- collect runtime, context switches, and energy if RAPL is readable

### 3. Decide real custom scheduler scope

There are two project paths:

- keep our algorithm as `custom_simulated` and use `custom_sched_ext` for real scheduler experiments
- implement our own sched_ext BPF scheduler

Recommendation:

- inspect installed sched_ext examples first
- choose the smallest working example as a base
- implement only a simple dynamic-quantum approximation if time allows

### 4. Add full `perf stat` wrapper

Current status:

- optional `perf_stat` collector is implemented and integrated into `run`/`compare` via `--perf-stat`
- captures task-clock, context-switches, cpu-migrations, page-faults, cycles, and instructions

Potential follow-up:

- add dedicated worker-wrapper execution mode for stricter process-tree accounting
- add configurable event sets for experiment profiles

Future goal:

- run a benchmark worker process under `perf stat -x ,`
- capture metrics such as task-clock, context-switches, cpu-migrations, page-faults

Reason:

- `resource.getrusage` is useful, but `perf stat` is more standard for reports

### 5. Expand results querying depth

Current status:

- `uv run energy-scheduler results` is implemented
- supports filters (`--scheduler`, `--workload`), `--run-id`, date range (`--from-time`, `--to-time`), and sort options (`--sort-by`, `--sort-order`)

Potential follow-up:

- add dedicated summary/detail schema for API consumption

### 6. Expand backend API depth

Current status:

- FastAPI backend API is implemented
- endpoints include workloads, run benchmark, compare schedulers, list saved results, fetch run details, and doctor
- async job mode is implemented via `/jobs/run`, `/jobs/compare`, and `/jobs/{job_id}`
- results endpoint supports date-range and sort query parameters

Potential follow-up:

- expand dedicated API response schemas for frontend stability
- add auth/rate-limit if exposed beyond localhost

### 7. Build local dashboard (Now Active)

Backend status is now sufficient to start UI implementation.

UI Phase 1 goals:

- consume `/workloads`, `/doctor`, `/run`, `/compare`, `/results`, `/results/{run_id}`
- support async flows via `/jobs/run`, `/jobs/compare`, `/jobs/{job_id}` for long runs

Initial UI should show:

- workload selector
- scheduler selector
- run button
- comparison table
- energy/runtime/context switch charts
- schedule timeline for `custom_simulated`
- saved runs history with filters/sort

## Current Stage

Backend is complete for non-UI scope.

Remaining system-side blocker:

- RAPL permissions still need host configuration for real joule claims.

Next implementation stage:

- build the local dashboard on top of the existing backend API.
