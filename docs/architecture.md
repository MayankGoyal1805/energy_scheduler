# Backend Architecture

## Why We Started With the Backend Skeleton

At this stage, building a UI would only hide missing design decisions. The project needs clear backend
boundaries first, because later we want to plug in:

- real workload generators
- real collectors such as RAPL and `perf`
- different scheduler modes
- a local website without rewriting the core logic

That is why the first implementation step is a backend skeleton with explicit interfaces.

## What We Built

The initial backend has these parts:

- a CLI entrypoint
- configuration objects
- shared data models
- workload abstractions
- collector abstractions
- scheduler adapter abstractions
- a benchmark runner
- SQLite persistence

All of this currently uses only the Python standard library. That is intentional. It keeps the first
version easy to run and easy to understand before we add Linux-specific integrations.

## Directory Layout

The important source files are:

- [src/energy_scheduler/cli.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/cli.py:1)
- [src/energy_scheduler/config.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/config.py:1)
- [src/energy_scheduler/models.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/models.py:1)
- [src/energy_scheduler/runner.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/runner.py:1)
- [src/energy_scheduler/storage.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/storage.py:1)
- [src/energy_scheduler/workloads/base.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/workloads/base.py:1)
- [src/energy_scheduler/workloads/synthetic.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/workloads/synthetic.py:1)
- [src/energy_scheduler/collectors/base.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/base.py:1)
- [src/energy_scheduler/collectors/runtime.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/collectors/runtime.py:1)
- [src/energy_scheduler/schedulers/base.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/schedulers/base.py:1)
- [src/energy_scheduler/schedulers/default.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/schedulers/default.py:1)

## Core Design Idea

The benchmark system is designed around a simple separation of concerns:

1. A workload defines what tasks should exist and how they behave.
2. A scheduler adapter defines how the system switches into a scheduling mode.
3. Collectors measure useful metrics around the run.
4. The runner coordinates the full lifecycle.
5. Storage persists the run so the later UI can query it.

This matters because the project will evolve in stages.

Today:

- workloads are synthetic Python processes
- collectors are simple runtime and system snapshots
- the scheduler adapter is only the Linux default no-op implementation

Later:

- workloads can stay the same or become richer
- collectors can add RAPL, `perf`, and trace data
- scheduler adapters can add `sched_ext` support
- the web app can call the same runner code through an API

## Shared Models

The models in [models.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/models.py:1)
are the contract between parts of the system.

### `TaskPhase`

A task is modeled as a sequence of phases, where each phase is either:

- `cpu`
- `sleep`

This is useful because it gives us one representation that can express:

- CPU-bound work
- interactive work
- bursty periodic work
- mixed behavior

### `TaskSpec`

`TaskSpec` describes one task:

- task identifier
- priority
- a tuple of phases

Even though the current Python execution does not directly apply kernel priorities, keeping the field
now is important because our future scheduler logic will likely use it.

### `TaskTiming`

`TaskTiming` records:

- arrival time
- first start time
- finish time

From those timestamps, the model computes:

- waiting time
- turnaround time
- response time

These are standard scheduler evaluation metrics, so we encode them directly in the model instead of
recomputing them in random places.

### `WorkloadExecution`

One workload can be repeated multiple times. `WorkloadExecution` captures one repetition and computes
its average timings across tasks.

### `BenchmarkRun`

`BenchmarkRun` is the top-level object for one CLI run. It stores:

- workload choice
- scheduler choice
- input parameters
- all repetitions
- collector readings

It also exposes summary averages. This is the object the UI will later display.

## Workloads

The workload abstraction lives in
[workloads/base.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/workloads/base.py:1).

Each workload must:

- build a set of tasks
- execute them and return a `WorkloadExecution`

The current implementation in
[workloads/synthetic.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/workloads/synthetic.py:1)
uses Python `multiprocessing` with the `spawn` start method.

### Why `multiprocessing`?

Threads would be distorted by the Python GIL for CPU-heavy work. We want actual concurrent OS-level
workers so the Linux scheduler has something real to schedule. Processes are therefore the correct
starting point.

### How synthetic execution works

Each task runs in its own process.

The parent process:

- creates all worker processes
- holds a start gate
- releases all workers together
- listens on a queue for start and finish timestamps

Each worker process:

- waits for the common start signal
- reports its actual start time
- executes its phase list
- reports its finish time

This gives us basic but real timing data.

### Why use CPU and sleep phases?

Because they let us approximate different scheduling patterns without writing four completely separate
engines.

Examples:

- CPU-bound: one long `cpu` phase
- interactive: short `cpu`, short `sleep`, short `cpu`
- bursty periodic: repeating small `cpu` and `sleep` phases
- mixed: a variety of the above

## Collectors

Collectors are small components that observe the run lifecycle.

The interface is intentionally tiny:

- `start()`
- `stop()`

The current collectors are:

- `RuntimeCollector`
- `SystemInfoCollector`

### Why this abstraction matters

Later we want collectors for:

- Intel RAPL energy readings
- `perf stat`
- scheduler tracepoints

Those collectors may need setup and teardown around a run. By giving them a lifecycle now, we avoid
rewriting the runner later.

## Scheduler Adapters

The scheduler abstraction is in
[schedulers/base.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/schedulers/base.py:1).

Right now the only implementation is:

- `LinuxDefaultScheduler`

It does nothing in `prepare()` and `cleanup()`, because the default scheduler is already active.

### Why create a no-op adapter?

Because it gives the runner a uniform contract. Later, a `sched_ext` adapter can:

- switch to a custom scheduler in `prepare()`
- restore the default scheduler in `cleanup()`

The runner should not care how that happens. It should only know that a scheduler mode exists.

## The Runner

The runner in [runner.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/runner.py:1)
is the orchestrator.

Its job is:

1. choose the workload
2. choose the scheduler adapter
3. start collectors
4. execute the workload repetitions
5. stop collectors
6. package everything into a `BenchmarkRun`

This is the most important backend seam. Later, the web API should simply call into the same runner.

## Storage

The SQLite storage in [storage.py](/home/mayank/repos/energy_scheduler/src/energy_scheduler/storage.py:1)
is deliberately simple.

For now, we store:

- identifying fields separately
- the full serialized run payload as JSON

Why store JSON early?

- it is easy to inspect
- it is flexible while the schema is still evolving
- it avoids premature normalization while we are still learning what fields matter

Later, if querying becomes more advanced, we can normalize more of the schema.

## CLI

The CLI gives us an immediate way to test the backend without building a web app.

Current commands:

- `uv run energy-scheduler workloads`
- `uv run energy-scheduler run --workload cpu_bound --save`
- `uv run energy-scheduler run --workload cpu_bound --perf-stat`
- `uv run energy-scheduler compare --workload mixed --save`
- `uv run energy-scheduler results --limit 20 --sort-by average_runtime_s`
- `uv run energy-scheduler doctor`
- `uv run energy-scheduler serve --host 127.0.0.1 --port 8000`

This is important because the CLI is our shortest feedback loop while the architecture is still
changing.

## Current Gaps

This backend now supports RAPL collection, optional `perf stat`, real sched_ext switching, and HTTP
API endpoints. The main remaining non-UI gaps are:

- RAPL readability permissions are still blocked in this environment, so real joule claims are not yet possible
- `perf stat` can be tightened further with a dedicated worker-wrapper mode for stricter process-tree accounting
- no custom BPF sched_ext scheduler has been implemented yet

## Why This Is A Good First Step

A common mistake in project work is to jump straight into final features. That usually creates a
messy codebase with no boundaries.

This backend skeleton solves that by establishing:

- one place for workload definitions
- one place for scheduler switching
- one place for metric collection
- one place for orchestration
- one place for persistence

That makes the next steps much safer.

## Next Recommended Step

The most meaningful next backend step is now experiment quality:

1. fix RAPL permissions on the host machine
2. run longer repeated comparisons with real sched_ext mode
3. decide whether to keep simulated policy + sched_ext experiments, or implement a custom BPF sched_ext scheduler
