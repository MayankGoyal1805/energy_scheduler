# Real Custom Scheduling With `sched_ext`

## Why `sched_ext`

To really run our custom scheduler, we need Linux to load a scheduler implementation instead of only
simulating one.

The best path for this project is `sched_ext`.

`sched_ext` lets Linux run scheduler policies implemented with BPF without rebuilding the whole
kernel. This is much more practical than patching `kernel/sched/` and recompiling Linux.

## Current Project Modes

The project currently has:

```text
linux_default      real Linux execution under the default scheduler
custom_simulated   Python simulation of our proposed scheduler
```

The target real mode is:

```text
custom_sched_ext   real workload execution while a sched_ext scheduler is active
```

## Environment Checks

We added a doctor command:

```bash
uv run energy-scheduler doctor
```

Machine-readable mode:

```bash
uv run energy-scheduler doctor --json
```

The doctor checks:

- kernel version
- `/sys/kernel/sched_ext`
- current `sched_ext` state
- `scxctl`
- `bpftool`
- `perf`
- available sched_ext schedulers from `scxctl list`
- RAPL readability

## What The Checks Mean

### Kernel

The kernel must support `sched_ext`.

On CachyOS, this is likely because CachyOS ships recent kernels and sched-ext tooling.

### `/sys/kernel/sched_ext`

This path means the kernel exposes the sched_ext interface.

Example:

```text
/sys/kernel/sched_ext
```

If this path is missing, we cannot use sched_ext on that booted kernel.

### `scxctl`

`scxctl` is a command-line client used to interact with `scx_loader`.

It can:

- list supported schedulers
- start a scheduler
- switch schedulers
- stop a running scheduler
- restore the default scheduler

### `bpftool`

`bpftool` is useful for BPF inspection and debugging.

We may not call it directly in the first scheduler adapter, but its presence is a good sign that the
system has BPF tooling installed.

### RAPL

RAPL is separate from sched_ext.

It is used to measure energy, not to run the scheduler.

It may require extra permissions depending on the system configuration.

## What We Found On This Machine

The detected kernel is:

```text
6.19.11-1-cachyos
```

The system exposes:

```text
/sys/kernel/sched_ext
```

`scxctl` and `bpftool` are installed.

`scxctl list` reports schedulers such as:

```text
beerland, bpfland, cake, cosmos, flash, lavd, pandemonium, p2dq, tickless, rustland, rusty
```

That means the real sched_ext path is viable.

## Next Implementation Step

The next backend step is to add a `custom_sched_ext` scheduler adapter.

That adapter should:

1. record the current scheduler state
2. start or switch to a chosen sched_ext scheduler using `scxctl`
3. run the benchmark workload normally
4. stop or restore the scheduler afterward

The first version should probably use an existing installed scheduler such as `scx_lavd` or the
corresponding `scxctl` scheduler name.

## Implemented Adapter

The project now includes:

- [src/energy_scheduler/schedulers/sched_ext.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/schedulers/sched_ext.py:1)

The adapter runs:

```bash
scxctl start --sched lavd
```

before the workload, and:

```bash
scxctl stop
```

after the workload.

The default sched_ext scheduler is:

```text
lavd
```

You can choose another installed scheduler:

```bash
uv run energy-scheduler run \
  --scheduler custom_sched_ext \
  --sched-ext-scheduler flash \
  --workload mixed
```

Compare default Linux against a real sched_ext scheduler:

```bash
uv run energy-scheduler compare \
  --candidate-scheduler custom_sched_ext \
  --sched-ext-scheduler lavd \
  --workload mixed
```

After that works, we can decide whether to write our own scheduler program or frame our project as:

- custom simulated scheduler design
- real sched_ext experimentation with available schedulers
- Linux default comparison

## Safety Rule

Scheduler switching affects the whole system.

So the adapter must always restore the scheduler in `cleanup()`, even if the workload crashes.

The existing runner already calls scheduler cleanup in a `finally` block, which is why we added that
abstraction early.

Even with this safety behavior, use short workloads first when testing sched_ext switching.
