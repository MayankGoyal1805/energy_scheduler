# CLI Reference

This document explains every CLI command and option in detail.

The entrypoint is:

```bash
uv run energy-scheduler <command> [options]
```

## Global Notes

- All runtime commands execute locally and may spawn child processes.
- `custom_sched_ext` changes system scheduling during the benchmark window.
- `custom_simulated` is a model, not kernel scheduler switching.
- `--save` writes full JSON payloads into SQLite at `data/benchmark_runs.sqlite3` by default.

## Command: `workloads`

List all available workload names.

```bash
uv run energy-scheduler workloads
```

## Command: `doctor`

Run environment diagnostics for benchmark readiness.

```bash
uv run energy-scheduler doctor
uv run energy-scheduler doctor --json
```

Checks include:

- kernel version
- sched_ext sysfs availability/state
- scxctl / bpftool / perf presence
- installed sched_ext scheduler list via scxctl
- RAPL readability

## Command: `run`

Execute a single benchmark run.

```bash
uv run energy-scheduler run [options]
```

### Options

- `--workload`:
  - workload name
  - default: `cpu_bound`

- `--scheduler`:
  - scheduler mode
  - default: `linux_default`
  - values used in project: `linux_default`, `custom_simulated`, `custom_sched_ext`

- `--sched-ext-scheduler`:
  - installed sched_ext scheduler name for `custom_sched_ext`
  - default: `cake`

- `--sched-ext-args`:
  - optional argument string passed to selected sched_ext scheduler via `scxctl --args=...`
  - useful for dynamic slice/quantum tuning

- `--tasks`:
  - number of tasks
  - default: `4`

- `--task-seconds`:
  - CPU budget per CPU burst
  - default: `0.25`

- `--repetitions`:
  - repeated executions per run
  - default: `1`

- `--db`:
  - SQLite path for persisted runs
  - default: `data/benchmark_runs.sqlite3`

- `--save`:
  - persist run to SQLite

- `--perf-stat`:
  - enable optional `perf_stat` collector

### Examples

```bash
uv run energy-scheduler run --workload cpu_bound
uv run energy-scheduler run --scheduler custom_simulated --workload mixed --tasks 8 --task-seconds 0.2
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler bpfland --sched-ext-args='--slice-us 2000 --slice-min-us 500 --throttle-us 200 --primary-domain powersave' --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3
```

## Command: `compare`

Run baseline and candidate schedulers with identical workload parameters.

```bash
uv run energy-scheduler compare [options]
```

Behavior:

- baseline is always `linux_default`
- candidate defaults to `custom_simulated`
- candidate can be switched to `custom_sched_ext`
- `custom_sched_ext` runs an installed third-party sched_ext scheduler (for example `cake`), not our custom algorithm

Interpretation:

- `custom_simulated` is our energy-aware dynamic-quantum algorithm in Python simulation form
- `custom_sched_ext` is real kernel scheduler switching via `scxctl`
- if you want to evaluate our algorithm behavior, use `--candidate-scheduler custom_simulated`
- if you want real Linux scheduler switching experiments, use `--candidate-scheduler custom_sched_ext --sched-ext-scheduler <installed_name>`

### Options

- `--workload`
- `--tasks`
- `--task-seconds`
- `--repetitions`
- `--db`
- `--save`
- `--json`
- `--candidate-scheduler`:
  - `custom_simulated` or `custom_sched_ext`
- `--sched-ext-scheduler`
- `--sched-ext-args`
- `--perf-stat`

### Examples

```bash
uv run energy-scheduler compare --workload mixed --tasks 4 --task-seconds 0.05
uv run energy-scheduler compare --candidate-scheduler custom_simulated --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --save
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler bpfland --sched-ext-args='--slice-us 2000 --slice-min-us 500 --slice-us-lag 50000 --throttle-us 200 --primary-domain powersave' --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3
```

## Command: `search-energy`

Sweep multiple installed sched_ext schedulers and report which one uses less measured
RAPL package energy than `linux_default` for the same workload configuration.

```bash
uv run energy-scheduler search-energy [options]
```

Behavior:

- runs one `linux_default` baseline run
- runs one `custom_sched_ext(<name>)` run per candidate scheduler
- compares `rapl package_energy_j` against baseline
- prints best lower-energy candidate if one is found

Options:

- `--workload`
- `--tasks`
- `--task-seconds`
- `--repetitions`
- `--candidates` (comma-separated sched_ext scheduler names)
- `--db`
- `--save`
- `--perf-stat`

Example:

```bash
uv run energy-scheduler search-energy --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
```

## Command: `median-board`

Run repeated baseline/candidate trials and report medians so leaderboard results are
more stable than single-run snapshots.

```bash
uv run energy-scheduler median-board [options]
```

Behavior:

- runs `linux_default` once per trial
- runs each candidate `custom_sched_ext(<name>)` once per trial
- computes median energy/runtime/delta vs baseline across successful samples
- reports sample counts and failed trial counts per row

Options:

- `--workload`
- `--tasks`
- `--task-seconds`
- `--repetitions`
- `--trials`
- `--candidates` (comma-separated sched_ext scheduler names)
- `--progress` / `--no-progress`
- `--perf-stat`
- `--json`

Examples:

```bash
uv run energy-scheduler median-board --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --trials 5
uv run energy-scheduler median-board --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --trials 7 --json
uv run energy-scheduler median-board --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --trials 7 --no-progress
```

## Command: `results`

Query persisted run history and inspect full payloads.

```bash
uv run energy-scheduler results [options]
```

### Listing Options

- `--limit`: max rows
- `--scheduler`: filter scheduler
- `--workload`: filter workload
- `--from-time`: inclusive lower created_at bound
- `--to-time`: inclusive upper created_at bound
- `--sort-by`:
  - `created_at`
  - `workload_name`
  - `scheduler_name`
  - `task_count`
  - `task_seconds`
  - `repetitions`
  - `average_runtime_s`
- `--sort-order`:
  - `asc` or `desc`
- `--json`: machine-readable list output

### Single Run Inspection

- `--run-id <id>` returns full saved payload JSON

### Examples

```bash
uv run energy-scheduler results --limit 20
uv run energy-scheduler results --scheduler linux_default --workload mixed
uv run energy-scheduler results --from-time 2026-04-14T00:00:00 --to-time 2026-04-15T00:00:00 --sort-by created_at --sort-order asc
uv run energy-scheduler results --sort-by average_runtime_s --sort-order asc --json
uv run energy-scheduler results --run-id <run_id>
```

## Command: `serve`

Start the local FastAPI backend.

```bash
uv run energy-scheduler serve [options]
```

### Options

- `--host`:
  - default: `127.0.0.1`
- `--port`:
  - default: `8000`
- `--reload`:
  - development autoreload

### Examples

```bash
uv run energy-scheduler serve
uv run energy-scheduler serve --host 0.0.0.0 --port 8000
uv run energy-scheduler serve --reload
```
