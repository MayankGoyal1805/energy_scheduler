# Energy Collection With RAPL

## Why Energy Collection Matters

The project title is:

Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment

That means runtime alone is not enough. We need a way to measure energy consumption while workloads
run. The first energy-specific collector is the RAPL collector.

## What RAPL Is

RAPL stands for Running Average Power Limit.

On many Intel systems, RAPL exposes energy counters for CPU power domains. Linux usually exposes
those counters through the powercap sysfs interface:

```text
/sys/class/powercap/
```

Common paths look like:

```text
/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
/sys/class/powercap/intel-rapl/intel-rapl:0:0/energy_uj
```

The `energy_uj` file stores an energy counter in microjoules.

## How We Use RAPL

The collector reads energy counters twice:

1. at the start of the benchmark
2. at the end of the benchmark

Then it subtracts:

```text
energy_used = end_energy_uj - start_energy_uj
```

That gives the energy consumed during the benchmark window.

## Why The Collector Uses Deltas

RAPL counters are cumulative. They do not reset for each process or benchmark.

So a single reading is not useful by itself. The useful value is the difference between two readings
around the workload.

## Counter Wraparound

RAPL counters can wrap around after reaching their maximum range.

Linux may expose:

```text
max_energy_range_uj
```

The collector uses this value when available. If the end counter is smaller than the start counter,
it assumes the counter wrapped and computes the wrapped delta.

## What RAPL Can And Cannot Tell Us

RAPL can tell us:

- package-level energy
- sometimes core-level or DRAM-level energy, depending on hardware
- average power during the run

RAPL cannot directly tell us:

- exact per-process energy
- exact per-thread energy
- exact energy used by one scheduling decision

For this project, that is still useful because we compare benchmark runs under controlled conditions.
If the workload and machine conditions are kept similar, total package energy is a meaningful metric.

## Current Implementation

The collector is implemented in:

- [src/energy_scheduler/collectors/rapl.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/rapl.py:1)

It is automatically included by the benchmark runner:

- [src/energy_scheduler/runner.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/runner.py:1)

The collector reports:

- whether RAPL is available
- discovered domain count
- energy per domain in microjoules and joules
- average power per domain
- total package energy if package domains are found

## If RAPL Is Missing

If no RAPL domains are visible, the collector does not crash.

If RAPL domains exist but cannot be read due to permissions, the collector also does not crash.

Instead, it returns an unavailable reading, for example:

```json
{
  "collector_name": "rapl",
  "metrics": {
    "available": 0,
    "reason": "cannot read /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj: Permission denied"
  }
}
```

This makes benchmark output honest and easy to debug.

## Troubleshooting

Check whether powercap exists:

```bash
find /sys/class/powercap -maxdepth 3 -type f | sort
```

If the directory exists but contains no `intel-rapl` files, possible reasons include:

- the kernel module is not loaded
- the current environment hides powercap
- the system is not exposing Intel RAPL counters
- permissions or container/sandbox restrictions are blocking access

On a normal CachyOS or Arch-based install on Intel hardware, the paths often appear automatically if
the kernel supports the hardware.

## Why We Add This Before The Custom Scheduler

Adding RAPL before the custom scheduler gives us a useful baseline first.

We can immediately run:

```bash
uv run energy-scheduler run --workload compression
```

and see whether energy data is available. Once the custom scheduler path exists, the same collector
will work for both default and custom runs.
