# Storage and Results Model

This document explains exactly what is stored, how queries work, and how to interpret results.

## Database

Default path:

```text
data/benchmark_runs.sqlite3
```

Table:

```text
benchmark_runs
```

Columns:

- `run_id` TEXT PRIMARY KEY
- `created_at` TEXT
- `workload_name` TEXT
- `scheduler_name` TEXT
- `task_count` INTEGER
- `task_seconds` REAL
- `repetitions` INTEGER
- `summary_json` TEXT

## Why JSON Payload Storage

The full benchmark payload is stored in `summary_json` to keep schema evolution flexible while the
project is still changing.

Benefits:

- no migration churn for each new collector field
- API and CLI can return rich detail immediately
- historical runs stay inspectable even as new metrics are added

Tradeoff:

- some computed sorting/filtering (like `average_runtime_s`) is done application-side.

## Stored Summary vs Full Payload

### Summary list (`results` listing)

Optimized row-level view with:

- id/time
- workload/scheduler
- task settings
- computed average runtime

### Full payload (`results --run-id`)

Includes:

- all execution timings
- all collector readings
- all schedule events (for simulated scheduler)
- computed summary metrics

## Timestamp Field

`created_at` is stored at save time.

Legacy rows can appear in older SQLite timestamp text format and newer rows in ISO-8601 with UTC
offset. Query filters normalize incoming values and still work across both styles.

## Results Query Features

Available in CLI and API:

- `scheduler_name` filter
- `workload_name` filter
- date range:
  - `from_time`
  - `to_time`
- sorting:
  - `created_at`
  - `workload_name`
  - `scheduler_name`
  - `task_count`
  - `task_seconds`
  - `repetitions`
  - `average_runtime_s`

## Metric Interpretation

`average_runtime_s`:

- average of repetition runtimes
- each repetition runtime is `finished_at_s - started_at_s`

`context_switches` in comparison:

- simulated mode uses simulated schedule event count
- real mode falls back to child process usage:
  - voluntary + involuntary switches

Energy fields:

- `estimated_energy_units` from `custom_simulated` are model units, not joules
- `rapl_package_energy_j` is real joules only when RAPL is readable

## Practical Query Patterns

Find recent runs:

```bash
uv run energy-scheduler results --limit 50 --sort-by created_at --sort-order desc
```

Find best runtime runs:

```bash
uv run energy-scheduler results --sort-by average_runtime_s --sort-order asc --limit 20
```

Filter one experiment window:

```bash
uv run energy-scheduler results --from-time 2026-04-14T00:00:00 --to-time 2026-04-15T23:59:59 --scheduler custom_sched_ext
```

Inspect one run deeply:

```bash
uv run energy-scheduler results --run-id <run_id>
```
