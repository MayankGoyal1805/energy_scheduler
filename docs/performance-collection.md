
# Performance Collection

The dashboard UI and backend both report all performance metrics described here. Only real schedulers are shown as candidates in the UI. For stable results, set CPU governor to `performance` and minimize background load.

## Why We Need Performance Metrics

Energy alone is not enough for scheduler comparison.

A scheduler can save energy by simply making work slower. That is not automatically a good result.
So every energy comparison needs performance metrics beside it.

The first performance metrics we collect are:

- child process CPU time
- page faults
- voluntary context switches
- involuntary context switches
- `perf` availability information
- parsed `perf stat` counters for the benchmark window (optional)

## Why We Started With `resource.getrusage`

Python exposes Linux child-process usage through:

```python
resource.getrusage(resource.RUSAGE_CHILDREN)
```

This gives accumulated usage for child processes created by the benchmark runner.

That matches our current workload model because each task runs as a child process.

## Metrics Collected

The collector is implemented in:

- [src/energy_scheduler/collectors/process_usage.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/process_usage.py:1)

It reports:

- `user_cpu_time_s`
- `system_cpu_time_s`
- `minor_page_faults`
- `major_page_faults`
- `voluntary_context_switches`
- `involuntary_context_switches`

## Voluntary vs Involuntary Context Switches

A voluntary context switch happens when a process gives up the CPU willingly.

Common reasons:

- sleeping
- waiting for I/O
- waiting for a lock

An involuntary context switch happens when the kernel preempts a process.

Common reasons:

- time slice expired
- a higher-priority task became runnable
- scheduler moved CPU time to another task

For scheduler experiments, involuntary context switches are especially interesting because they often
reflect scheduler-driven preemption.

## Why We Also Record `perf` Information

Linux `perf` is the standard tool for performance counters.

The project now records whether `perf` is available using:

- [src/energy_scheduler/collectors/perf_info.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/perf_info.py:1)

It reports:

- path to `perf`
- `perf --version`
- `/proc/sys/kernel/perf_event_paranoid`

This is useful because `perf` permissions vary by machine.

## About `perf_event_paranoid`

`perf_event_paranoid` controls what unprivileged users can measure.

Typical values:

- `-1`: most permissive
- `0`: allows CPU events but restricts raw/ftrace events
- `1`: restricts CPU events
- `2`: restricts kernel profiling
- higher values: more restrictive depending on distro/kernel policy

On this machine, `perf stat` for a direct user command works, but system-wide `perf -a` is blocked.
That is normal on many desktop distributions.

## Perf Stat Collector

The project now includes an optional `perf_stat` collector that runs while the benchmark executes.

Enable it in CLI:

```bash
uv run energy-scheduler run --workload cpu_bound --perf-stat
uv run energy-scheduler compare --workload mixed --perf-stat
```

It currently invokes `perf stat` with event CSV output and captures counters such as:

- `task-clock`
- `context-switches`
- `cpu-migrations`
- `page-faults`
- `cycles`
- `instructions`

The collector is implemented in:

- [src/energy_scheduler/collectors/perf_stat.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/perf_stat.py:1)

Current shape note:

- this wrapper attaches to the benchmark process during execution and parses perf output on stop
- a future worker-process wrapper mode can tighten process-tree isolation further

## How This Helps The Project

The output now includes timing, energy availability, and process usage metrics.

That lets us compare:

- runtime
- CPU time
- context switches
- page faults
- energy when RAPL is readable

This is enough to start building baseline data for the default Linux scheduler.

## Future Perf Enhancements

A stronger later version should add a command-wrapper mode:

```bash
perf stat -x , -e task-clock,context-switches,cpu-migrations,page-faults \
  -- uv run energy-scheduler worker-run ...
```

That can provide stricter process-tree boundary control for published benchmark reports.
