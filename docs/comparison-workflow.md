# Comparison Workflow

## Why We Added `compare`

Running one scheduler at a time is useful for debugging, but the project needs direct comparisons.

The `compare` command runs:

1. `linux_default`
2. a candidate scheduler (`custom_simulated` by default, or `custom_sched_ext`)

with the same workload parameters and prints a side-by-side summary.

## Command

```bash
uv run energy-scheduler compare --workload mixed --tasks 4 --task-seconds 0.05
```

Save both runs:

```bash
uv run energy-scheduler compare --workload mixed --tasks 4 --task-seconds 0.05 --save
```

Compare Linux default vs our simulated custom algorithm:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_simulated --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --save
```

Compare Linux default vs installed real sched_ext scheduler (for example lavd):

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler lavd --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
```

Machine-readable output:

```bash
uv run energy-scheduler compare --workload mixed --json
```

## What Gets Compared

The comparison currently includes:

- average runtime
- average waiting time
- average turnaround time
- average response time
- context switches
- estimated energy units from the simulated scheduler
- RAPL package energy if available

## Baseline vs Candidate

The baseline is:

```text
linux_default
```

This is a real workload execution under the normal Linux scheduler.

Default candidate is:

```text
custom_simulated
```

This is the Python simulation of our energy-aware dynamic quantum scheduler.

Alternative candidate:

```text
custom_sched_ext
```

This starts an installed sched_ext scheduler such as `lavd` for real kernel execution.

## Important Interpretation Rule

Do not overclaim this comparison.

The Linux baseline is real execution. The custom scheduler is currently simulated.

That means for `linux_default` vs `custom_simulated`:

- Linux timing numbers are real observed timings
- custom timing numbers are simulated model timings
- Linux RAPL energy is real if available
- custom energy units are relative model units, not joules

And for `linux_default` vs `custom_sched_ext`:

- both timing and RAPL energy values are real observed run values
- results reflect the installed sched_ext scheduler used (for example `lavd`)
- this is not yet our own custom BPF scheduler implementation

So this comparison is useful for showing algorithm behavior, but it is not yet a final kernel-level
energy comparison.

## Why This Is Still Useful

The compare command gives us the full project pipeline:

```text
same workload
  -> baseline scheduler
  -> custom scheduler
  -> metrics
  -> comparison table
```

That is exactly what the future web dashboard needs.

The UI can later call the same comparison logic instead of duplicating it.

For detailed interpretation guidance on why scheduler winners differ by workload and
how to classify schedulers against the project goal, see:

- [docs/scheduler-energy-analysis.md](/home/mayank/repos/energy_scheduler/docs/scheduler-energy-analysis.md:1)

## Implementation

Comparison helpers live in:

- [src/energy_scheduler/compare.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/compare.py:1)

The CLI command lives in:

- [src/energy_scheduler/cli.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/cli.py:1)

## Saved Results Inspection

You can inspect saved benchmark history directly from SQLite through the CLI.

List recent runs:

```bash
uv run energy-scheduler results --limit 20
```

Filter by scheduler or workload:

```bash
uv run energy-scheduler results --scheduler linux_default --workload mixed
```

Get machine-readable list output:

```bash
uv run energy-scheduler results --json
```

Inspect one saved run payload by ID:

```bash
uv run energy-scheduler results --run-id <run_id>
```
