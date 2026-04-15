
# Workloads

The dashboard UI and backend both support all workload types described here. Only real schedulers are shown as candidates in the UI; simulated schedulers are for algorithm/model comparison only.

**Reproducibility:** For stable results, set CPU governor to `performance` and minimize background load.

## Why We Need More Than One Workload Type

Schedulers behave differently depending on the kind of work the system is doing.

A scheduler that looks good for long CPU-bound jobs may behave badly for:

- short interactive jobs
- frequent wakeups
- mixed desktop-like activity

That is why the benchmark framework includes multiple workload categories instead of a single stress
test.

## Two Workload Families

The project now has two families of workloads:

1. synthetic workloads
2. lightweight application-style workloads

Both are useful, but for different reasons.

## Synthetic Workloads

Synthetic workloads are made from explicit `cpu` and `sleep` phases. They are useful when we want
clean, explainable scheduler behavior.

### `cpu_bound`

Pattern:

- one long CPU burst per task

What it represents:

- batch compute
- throughput-heavy execution

What it is good for:

- runtime comparisons
- showing contention between pure compute jobs

### `interactive_short`

Pattern:

- short CPU burst
- short sleep
- short CPU burst

What it represents:

- interactive tasks that wake frequently

What it is good for:

- response time
- scheduler overhead
- fairness under quick bursts

### `mixed`

Pattern:

- a blend of long CPU jobs and shorter burst-sleep tasks

What it represents:

- a rough desktop-style mixed workload

What it is good for:

- seeing how the scheduler handles competing behavior types at once

### `bursty_periodic`

Pattern:

- repeated short CPU bursts separated by sleeps

What it represents:

- timer-driven or periodic background tasks

What it is good for:

- wakeup-heavy behavior
- periodic scheduling overhead

## Lightweight Application-Style Workloads

These workloads are still fully automated, but they are shaped like real kinds of work a machine
actually does. We intentionally keep them local and dependency-free.

Important point:

- these do not launch GUI applications
- these do not require heavyweight benchmark suites
- these are small scripted workloads that produce real OS activity

That keeps the project manageable and reproducible.

### `compression`

What it does:

- each worker repeatedly compresses generated payload data using `lzma`
- each round also hashes the output

What it represents:

- CPU-heavy application work
- batch processing
- compute-dominant behavior

Why we included it:

- it feels closer to a real user task than a pure busy loop
- it is easy to automate and repeat

### `file_scan`

What it does:

- the benchmark creates a temporary directory tree
- each worker recursively scans and hashes its assigned files

What it represents:

- file indexing
- scanning source trees
- metadata and content processing workloads

Why we included it:

- it mixes filesystem access with CPU hashing
- it resembles lightweight developer or system maintenance tasks

### `local_request_burst`

What it does:

- the benchmark starts a small local HTTP server
- worker processes send short bursts of local requests and read JSON responses

What it represents:

- request/response style activity
- interactive or service-oriented work
- many short tasks with pauses between them

Why we included it:

- it creates short-lived, latency-sensitive activity
- it is local and repeatable

Operational note:

- this workload binds a temporary localhost server socket
- that works normally on a real Linux machine
- it may be blocked in restricted sandboxes

### `mixed_realistic`

What it does:

- some tasks do compression
- some tasks do file scanning
- some tasks send local requests

What it represents:

- a mixed machine state with different classes of work active at once

Why we included it:

- it is the closest thing in this project to a small “real system usage” workload
- it is a good candidate for final comparisons

Operational note:

- this workload also needs temporary localhost socket access because one part of it is request-based

## Why We Did Not Use Heavy Benchmarks

We intentionally did not start with tools like Cinebench or large benchmark suites.

Reasons:

- they take longer to run
- they are harder to integrate into a custom benchmark pipeline
- they are less transparent for learning
- they often make iteration slow

For this project, small automated workloads are a better engineering tradeoff.

## Why We Did Not Automate GUI Apps

It is possible to script GUI applications, but that adds a lot of instability:

- desktop environment differences
- focus and timing issues
- automation fragility
- extra dependencies

Since our real goal is scheduler comparison, GUI automation would add complexity without giving much
extra value.

## Current Scope Decision

The benchmark suite should focus on:

- a few synthetic workloads for scheduler clarity
- a few lightweight application-style workloads for realism

This is enough to support:

- timing comparisons
- energy comparisons later with RAPL
- clearer explanation in the report

## Next Step

The next technical step after workload design is to attach real Linux-side measurement to these runs:

1. Intel RAPL collector
2. `perf stat` collector

Those collectors will make the same workloads useful for energy and performance analysis, not just
timing.
