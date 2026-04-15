
# Custom Simulated Scheduler

The simulated scheduler (`custom_simulated`) is a Python model of our algorithm. It is not a real kernel scheduler and is not shown as a candidate in the dashboard UI. Use it for algorithm/model comparison only. For stable results, set CPU governor to `performance` and minimize background load.

## Why We Added A Simulated Scheduler First

The project eventually wants to compare Linux's default scheduler with our own energy-aware dynamic
quantum scheduler.

There are two ways to do that:

1. implement a real scheduler with `sched_ext`
2. simulate the scheduling policy in Python

The simulated path is the safer first step.

It lets us:

- define the algorithm clearly
- compare output against Linux baseline runs
- build the reporting pipeline
- avoid getting blocked by kernel or `sched_ext` setup early

## Scheduler Name

The new scheduler mode is:

```text
custom_simulated
```

Example command:

```bash
uv run energy-scheduler run --scheduler custom_simulated --workload mixed --tasks 4
```

## Important Limitation

This is not a real kernel scheduler.

It does not change what the Linux kernel does. Instead, it uses the workload's `TaskSpec` definitions
and computes how our proposed scheduler would order and slice those tasks.

That means:

- timing values are simulated
- energy values are model units, not joules
- no real process scheduling happens for this mode

This is still valuable because it gives us a precise model of our proposed algorithm.

## Algorithm Goal

The algorithm is an Energy-Aware Dynamic Quantum Scheduler.

Its goal is to adjust each task's time quantum based on:

- task priority
- task behavior
- estimated energy intensity

The scheduler tries to avoid giving large uninterrupted slices to CPU-heavy, energy-intensive tasks
while still protecting bursty or interactive tasks from starvation.

## Task Inputs

Each task has:

- `task_id`
- `priority`
- a list of phases

Each phase is either:

- `cpu`
- `sleep`

From the phase list, the scheduler can estimate whether the task is:

- CPU-heavy
- bursty
- mixed

## Dynamic Quantum Formula

The current implementation uses this structure:

```text
quantum = base_quantum * priority_factor * behavior_factor / energy_factor
```

The scoring is now EDP-style (energy-delay tradeoff inspired): tasks with higher
estimated energy intensity are deprioritized unless priority pressure is strong.

Where:

- `base_quantum` is the base slice length
- `priority_factor` increases the quantum for higher-priority tasks
- `behavior_factor` adjusts the quantum based on task pattern
- `energy_factor` penalizes CPU-heavy tasks

The implementation is in:

- [src/energy_scheduler/schedulers/simulated.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/schedulers/simulated.py:1)

## Priority Factor

Linux-style priorities use lower numbers for higher priority.

The simulated scheduler clamps priorities into a simple range and computes:

```text
priority_factor = 1.0 + ((139 - priority) / 59)
```

That means:

- lower priority number gets a larger factor
- higher priority number gets a smaller factor

This keeps priority meaningful without making it dominate everything.

## Behavior Factor

The behavior factor is based on the phase pattern.

Current rules:

- pure CPU-bound tasks get a smaller factor
- tasks with sleep phases get a larger factor
- highly bursty tasks get the largest factor

This is meant to protect interactive or bursty workloads.

## Energy Factor

The current energy factor is:

```text
energy_factor = 1.0 + cpu_ratio
```

Where:

```text
cpu_ratio = cpu_time / total_task_time
```

So a pure CPU-bound task gets a higher energy factor than a task that sleeps often.

## Over-Utilization Fallback

Inspired by Linux EAS over-utilization behavior, the simulated policy reduces
energy bias when the workload is highly CPU-heavy.

Current behavior:

- computes average task CPU ratio
- if ratio >= 0.8, it favors throughput/fairness by reducing energy-based penalties

This avoids aggressive energy-biased scheduling under sustained CPU saturation.

This is a simple model. It is not real joule measurement. Real energy measurement comes from RAPL
during actual Linux runs.

## Source Inspiration

The simulated policy shape is inspired by publicly documented Linux scheduling
principles, not copied kernel code:

- Linux Energy-Aware Scheduling concepts: https://docs.kernel.org/scheduler/sched-energy.html
- sched_ext architecture and custom scheduler model: https://docs.kernel.org/scheduler/sched-ext.html

## Scheduling Loop

The simulated scheduler repeats this process:

1. find tasks with remaining CPU work
2. rank them by energy-aware score
3. compute a dynamic quantum for the selected task
4. run it for that quantum or until it finishes
5. record a schedule event
6. repeat until all tasks are complete

Each schedule event records:

- task id
- start time
- finish time
- quantum used
- priority
- energy factor

## Output

The normal benchmark output now includes:

- simulated task timings
- simulated schedule events
- simulated context switch count
- estimated energy units

The collector named `custom_simulated_scheduler` reports:

```json
{
  "available": 1,
  "context_switches": 12,
  "estimated_energy_units": 0.123,
  "note": "relative model units, not joules"
}
```

## How This Fits The Project

Now the project has two sides:

- `linux_default`: real workload execution under Linux
- `custom_simulated`: proposed scheduling policy simulated from the same workload definitions

This is enough to start building comparison commands and eventually dashboard graphs.

## Next Step

The next practical step is to add a `compare` CLI command that runs:

1. `linux_default`
2. `custom_simulated`

for the same workload and prints a side-by-side summary.

That will make the project easier to demo even before we build the web UI.
