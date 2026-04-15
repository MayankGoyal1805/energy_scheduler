# Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment

This document is a complete, detailed project description and presentation guide for the Energy Scheduler project. It is written so you can explain the system end-to-end, defend technical choices, answer common questions, and present results credibly even when scheduler outcomes vary by workload.

---

## 1. Executive Summary

### 1.1 What this project is

This project is a reproducible benchmarking and analysis platform for studying energy-performance tradeoffs in CPU scheduling. It compares Linux default scheduling against:

1. A modeled algorithm (`custom_simulated`) representing our energy-aware dynamic quantum concept.
2. Real sched_ext scheduler switching (`custom_sched_ext`) using installed Linux sched_ext schedulers (for example `bpfland`, `cake`, `lavd`).

### 1.2 What makes it valuable now

The project is not "just comparisons". It already delivers a complete engineering pipeline:

1. Controlled workload generation (synthetic + realistic lightweight application-style).
2. Real metric collection (runtime, context switches, RAPL energy when available, perf information and optional perf stat).
3. Repeatable comparison methodology (median-board trials for robustness).
4. Storage and query layer (SQLite, filter/sort/date queries).
5. API and dashboard for practical usage.
6. Strict caching for median-board runs to avoid redundant execution.

### 1.3 The honest current state

1. `custom_simulated` is a model of the algorithm, not kernel-level replacement.
2. `custom_sched_ext` proves real kernel scheduler switching and benchmarking works.
3. Third-party sched_ext schedulers are comparative candidates, not our custom implementation.
4. Real joule claims depend on RAPL permissions.

---

## 2. Project Goal and Problem Statement

### 2.1 Goal

Design and evaluate an energy-aware scheduling strategy that dynamically adjusts task quantum/slice behavior based on workload characteristics and intensity.

### 2.2 Why this matters

Default schedulers optimize for broad system behavior and fairness. They are not tuned for one explicit objective like minimizing energy for a specific mixed workload profile while keeping runtime acceptable.

### 2.3 Core challenge

There is no universal scheduler winner. Different policies win on different workloads and under different system states. Therefore, the project must measure tradeoffs robustly, not rely on one-off runs.

---

## 3. Technology Stack and Tooling

### 3.1 Language and packaging

1. Python project with entrypoint script `energy-scheduler`.
2. Managed via `uv` for environment + execution consistency.
3. Project metadata in `pyproject.toml`.

### 3.2 Backend

1. FastAPI for HTTP endpoints.
2. Uvicorn for local serving.
3. Standard library plus project modules for runner/storage/collectors.

### 3.3 Data and persistence

1. SQLite database (`data/benchmark_runs.sqlite3`).
2. JSON payload storage for flexible schema evolution.
3. Dedicated `median_runs` table for cached leaderboard computations.

### 3.4 System-facing tools

1. `scxctl` for sched_ext scheduler start/stop/list interactions.
2. RAPL sysfs paths for energy counters (`/sys/class/powercap/.../energy_uj`).
3. `perf` availability probing and optional `perf stat` capture.

### 3.5 Frontend

1. Local dashboard served by backend.
2. Plotly-based chart rendering.
3. Async job polling for long-running operations.

---

## 4. Architecture Overview

### 4.1 Core layers

1. **Workloads**: define and execute benchmark task patterns.
2. **Schedulers**: adapter layer for default, simulated, and sched_ext modes.
3. **Collectors**: runtime/system/energy/performance telemetry.
4. **Runner**: orchestrates scheduler lifecycle, workload execution, and collector windows.
5. **Storage**: persists runs and cached median leaderboard results.
6. **Interfaces**: CLI + API + dashboard all reuse the same backend core.

### 4.2 Why this architecture works

1. Clear boundaries keep experiments reproducible.
2. New workloads/collectors/schedulers are pluggable.
3. API and CLI remain consistent because they call the same execution path.
4. UI is presentation-only, not business-logic-heavy.

---

## 5. Workloads: What is implemented and why

### 5.1 Synthetic workloads

1. `cpu_bound`
2. `interactive_short`
3. `mixed`
4. `bursty_periodic`

These are controlled phase-based workloads (CPU/sleep composition) useful for understanding scheduler behavior mechanics.

### 5.2 Application-style lightweight workloads

1. `compression`
2. `file_scan`
3. `local_request_burst`
4. `mixed_realistic`

These approximate practical machine activity without requiring heavyweight external suites.

### 5.3 Why both families are needed

1. Synthetic workloads improve interpretability.
2. Application-style workloads improve realism.
3. Together they reveal where winners are robust and where they are workload-sensitive.

---

## 6. Scheduler Modes and Their Meaning

### 6.1 `linux_default`

Real execution under default Linux scheduling (baseline).

### 6.2 `custom_simulated`

Model-only simulation of an energy-aware dynamic-quantum policy.

Key formula shape used in the model:

quantum = base_quantum * priority_factor * behavior_factor / energy_factor

Important:

1. It does not switch kernel scheduler.
2. It provides schedule events and relative model energy units.

### 6.3 `custom_sched_ext`

Real scheduler switching via sched_ext and `scxctl`.

Typical flow:

1. Start chosen sched_ext scheduler.
2. Execute workload.
3. Stop scheduler in cleanup.

Important:

1. This validates real-kernel experimentation pipeline.
2. Installed schedulers are references, not your custom algorithm implementation.

---

## 7. Collectors and Metrics

### 7.1 Runtime and system context

1. Runtime window measurement.
2. System info snapshot.

### 7.2 RAPL energy collection

1. Reads package-domain counters from powercap sysfs.
2. Uses start/stop delta approach.
3. Handles wraparound.
4. Returns unavailable status cleanly on permission issues.

### 7.3 Process usage collection

Uses `resource.getrusage(RUSAGE_CHILDREN)` for:

1. User/system CPU time.
2. Minor/major page faults.
3. Voluntary/involuntary context switches.

### 7.4 Perf information and optional perf-stat

1. Detects `perf` availability and system paranoid setting.
2. Optional perf-stat captures standard counters such as:
   - task-clock
   - context-switches
   - cpu-migrations
   - page-faults
   - cycles
   - instructions

---

## 8. Benchmark Execution Flow

For each run:

1. Build scheduler adapter from settings.
2. Call scheduler `prepare()`.
3. Start collectors.
4. Execute workload repetitions.
5. Stop collectors.
6. Call scheduler `cleanup()` in `finally` to ensure safety.
7. Aggregate into a `BenchmarkRun` model.
8. Optionally persist to SQLite.

For simulated mode:

1. Generate simulated executions and schedule events.
2. Append a synthetic collector reading with model context-switches and model energy units.

For sched_ext mode:

1. Append scheduler metadata collector reading (start/stop metadata).

---

## 9. CLI Surface and Workflow

Main commands:

1. `workloads`
2. `doctor`
3. `run`
4. `compare`
5. `search-energy`
6. `median-board`
7. `results`
8. `serve`

### 9.1 Why this matters in presentation

This demonstrates the project is operationally complete, not a notebook-only prototype.

---

## 10. API Surface and Async Job System

Key endpoints:

1. `GET /health`
2. `GET /workloads`
3. `GET /sched-ext-candidates`
4. `GET /doctor`
5. `POST /run`
6. `POST /compare`
7. `POST /median-board`
8. `POST /median-runs/query`
9. `POST /jobs/run`
10. `POST /jobs/compare`
11. `POST /jobs/median-board`
12. `GET /jobs/{job_id}`
13. `GET /jobs/{job_id}/logs`
14. `GET /results`
15. `GET /results/{run_id}`

### 10.1 Async execution model

1. Thread-pool backed job queue (`queued -> running -> completed/failed`).
2. Timestamped incremental logs.
3. Pollable status API for UI and automation.

### 10.2 Why this is important

Long benchmark trials are first-class workflows, not blocking HTTP calls.

---

## 11. Storage Model and Caching Strategy

### 11.1 Tables

1. `benchmark_runs`
2. `median_runs`

### 11.2 Cached median query behavior

`/median-runs/query` checks for exact-parameter matches:

1. workload
2. tasks
3. task_seconds
4. repetitions
5. trials
6. sorted candidate set
7. perf_stat flag

If found, cached result is returned; otherwise `/jobs/median-board` can compute and persist a new median entry.

### 11.3 Why this is a strong design choice

1. Eliminates redundant expensive trial execution.
2. Preserves reproducibility by parameterized keying.
3. Speeds up dashboard and iterative exploration.

---

## 12. Dashboard UI Behavior

### 12.1 What it does

1. Global config for trials/repetitions/candidates/workloads.
2. Aggregate charts for cross-workload scheduler view.
3. Per-workload block charts and compact table.
4. Live job logs.

### 12.2 Important recent behavior detail

`Update Target` for a workload block can force fresh rerun instead of silently using cached result, allowing explicit re-execution when desired.

---

## 13. Methodology: How to explain experimental rigor

### 13.1 Why medians

Scheduler behavior is noisy due to:

1. thermal drift
2. background tasks
3. frequency/governor interactions
4. workload phase interactions

Median across repeated trials is more robust than single-run outcomes.

### 13.2 Primary and secondary metrics

1. Primary: RAPL package energy joules (`median_energy_j`).
2. Secondary: runtime (`median_runtime_s`).
3. Comparative: delta percent vs baseline (`median_delta_percent`).
4. Reliability: failed-trial count.

### 13.3 Honest interpretation pattern

1. No universal winner expected.
2. Mixed outcomes are normal in multi-objective scheduling.
3. Robust candidates are those with strong median profile and acceptable runtime tradeoff.

---

## 14. Positioning bpfland without overclaiming

### 14.1 What to say

1. In current benchmark profile, bpfland is a strong practical candidate by median score.
2. It exhibits dynamic slice behavior and tunable knobs aligned with project direction.
3. It may not win every single workflow, which is expected.

### 14.2 What not to say

1. bpfland is universally best.
2. bpfland is your custom scheduler implementation.

### 14.3 Correct project message

1. Your project built the complete methodology and tooling.
2. Third-party sched_ext schedulers are comparative references.
3. Next step is custom BPF sched_ext policy implementation guided by this evidence.

### 14.4 How bpfland works (practical explanation for presentation)

`bpfland` is a sched_ext policy with a vruntime-style fairness foundation and tunable dispatch behavior. In presentation terms, explain it as:

1. **Runnable queue management**:
   - tasks are tracked with fairness-oriented accounting (vruntime-like behavior)
   - interactive or recently woken tasks can be favored to reduce visible latency
2. **Dispatch/slice behavior**:
   - tasks receive execution slices that are not fixed forever; behavior depends on runnable pressure and policy knobs
   - this creates a practical "dynamic quantum" effect, even though implementation details differ from your simulated formula
3. **Energy-relevant knobs**:
   - controls such as throttling or domain preferences can bias placement/execution behavior
   - these knobs can reduce power in some situations but can also increase total runtime if over-constrained
4. **Why it fits your project direction**:
   - it is one of the better real sched_ext proxies for dynamic behavior under mixed workloads
   - it often gives strong median outcomes in your board while still showing realistic variability

How to say this in one line:

- "bpfland gives us a real-kernel, tunable, fairness-plus-dynamic-slice candidate that aligns with our energy-aware dynamic-quantum direction better than a static-policy baseline."

### 14.5 EAS context: what to mention about energy-aware scheduling approaches

When you say "EAS algos," keep the distinction clear:

1. **Linux EAS (Energy-Aware Scheduling) in mainline scheduler**:
   - this is kernel-integrated capacity + energy-model-aware task placement logic
   - it is most impactful on asymmetric systems (especially ARM big.LITTLE)
2. **sched_ext policies (like bpfland/cake/cosmos/lavd)**:
   - these are pluggable scheduling policies via BPF
   - they are not equivalent to stock kernel EAS internals, but can express energy/latency/fairness tradeoffs through their own policy logic
3. **Your simulated algorithm (`custom_simulated`)**:
   - this is your conceptual policy model for dynamic quantum and energy sensitivity
   - it is a research/control layer that helps define the custom sched_ext policy you implement next

Useful presentation sentence:

- "We use EAS principles as design inspiration for energy-capacity tradeoffs, but our current kernel experiments are through sched_ext policy candidates and our own simulation model."

### 14.6 Why this would likely look even better on ARM

Your project can often show clearer energy-aware scheduling effects on ARM platforms, mainly because of hardware topology and power behavior:

1. **Asymmetric cores (big/LITTLE)**:
   - ARM SoCs commonly expose heterogeneous cores with clear energy/performance tradeoffs
   - scheduler placement decisions have a stronger, more visible energy impact
2. **EAS design alignment**:
   - Linux EAS was heavily developed for asymmetric capacity/energy domains
   - policy quality differences are easier to surface when CPU capacities are diverse
3. **Frequency and residency behavior**:
   - ARM mobile/embedded power states and cluster-level behaviors can amplify scheduling energy differences
4. **x86 caveat (your current environment)**:
   - many desktop x86 setups are more homogeneous for scheduler-visible capacity (or have different turbo behavior)
   - package-level RAPL is coarse and can blur per-policy differences for short runs

How to present this safely:

- "Our framework is architecture-agnostic, but ARM heterogeneous systems are expected to expose energy-aware scheduling gains more clearly."

### 14.7 Short technical notes on other algorithms in this project

Use this compact classification when asked "what about the others?":

1. **`linux_default`**:
   - baseline general-purpose scheduler behavior
   - strong reference point, not energy-first by explicit objective
2. **`cake`**:
   - fairness/latency-throughput balancing style with tunability
   - can be strong in some mixed workloads, not always lowest joules
3. **`cosmos`**:
   - locality-sensitive style behavior
   - can benefit cases where reducing migrations/cache disruption matters
4. **`lavd`**:
   - latency-oriented policy tendencies
   - may improve responsiveness but not guaranteed lowest energy
5. **`flash`, `beerland`, `p2dq`, `tickless`, `rustland`, `rusty`, `pandemonium`**:
   - useful comparative candidates to stress-test robustness of conclusions
   - winner status is workload-dependent and should be reported through medians

Important: emphasize that these are **benchmark reference policies**, while your project value is the **evaluation framework + algorithm-to-implementation path**.

### 14.8 How prioritization and "calculation" works in bpfland and other algorithms

This is the exact way to explain scheduler decision logic in viva/presentation without pretending we have hidden internal formulas for every third-party scheduler.

#### A) bpfland: how it prioritizes in practice

`bpfland` can be explained as a fairness-first scheduler with dynamic dispatch behavior and optional power-bias knobs.

At each scheduling decision, think of it as evaluating:

1. **Task fairness state** (vruntime-style pressure):
   - tasks that have run less recently are favored to preserve fairness.
2. **Interactivity/wakeup behavior**:
   - newly woken, short, or latency-sensitive tasks may get quicker service to reduce response lag.
3. **Runnable pressure and slice control**:
   - slice behavior adjusts with queue pressure and policy constraints (not a fixed one-size quantum).
4. **Optional energy-bias controls**:
   - knobs like throttle/domain preference can bias execution toward lower-power behavior.

So, in short, bpfland does not know exact future joules. It uses runtime signals to make a best-next decision repeatedly.

You can present its decision idea like this:

- "Pick runnable task with strongest fairness/latency need, then apply current dispatch/slice and placement policy constraints, then re-evaluate on next tick/wakeup."

#### B) Other algorithms: what they prioritize

For third-party sched_ext policies, present optimization intent and observed behavior, not exact private formulas.

1. **linux_default**:
   - prioritizes broad fairness and system responsiveness
   - energy is indirect outcome, not explicit first objective
2. **cake**:
   - prioritizes fairness/latency-throughput balancing with tunability
   - can trade runtime and energy differently per workload
3. **cosmos**:
   - prioritizes locality-sensitive behavior
   - often tries to reduce migration/cache disruption effects
4. **lavd**:
   - prioritizes latency-oriented execution behavior
   - can be strong on responsiveness, not always minimum joules
5. **flash / beerland / p2dq / tickless / rustland / rusty / pandemonium**:
   - each has different internal tradeoffs (fairness, latency, locality, wakeup handling)
   - treat them as candidate policies and evaluate through medians, not assumptions

#### C) Your own modeled algorithm (`custom_simulated`): explicit calculation logic

This is where you **can** give a clear formula, because it is your model:

quantum = base_quantum * priority_factor * behavior_factor / energy_factor

Interpretation:

1. **priority_factor**: protects higher-priority tasks.
2. **behavior_factor**: favors bursty/interactive patterns.
3. **energy_factor**: penalizes sustained CPU-intense tasks.

So your model is explicit dynamic quantum scheduling, while bpfland and other real schedulers are policy implementations with their own internal heuristics.

#### D) How to answer "but how does it calculate energy before running?"

Use this exact answer:

- "It does not predict exact joules beforehand. It uses observable runtime proxies (CPU intensity, wakeup pattern, fairness state, placement policy) to minimize expected energy-delay cost online; actual energy is measured afterward with RAPL for evaluation."

### 14.9 Are we showing real EAS right now? Can we show it?

Short answer:

1. **Right now in this project flow, you are not explicitly demonstrating stock kernel EAS internals.**
2. **You are demonstrating energy-aware benchmarking and sched_ext policy behavior.**
3. **Yes, you can show EAS directly, but only if host/kernel/hardware conditions support it clearly (best on ARM big.LITTLE).**

#### What you can honestly claim now

1. You have an energy-aware evaluation framework.
2. You can compare real schedulers under identical workloads with RAPL/runtime metrics.
3. You are using EAS principles as design inspiration, not claiming that bpfland equals stock EAS engine.

#### How to show real EAS explicitly (recommended plan)

To demonstrate EAS as a first-class part of results, do this on an ARM heterogeneous system:

1. Ensure kernel has relevant scheduler energy-model support and topology capacity data.
2. Use governors/settings that allow meaningful placement/frequency behavior (`schedutil` usually).
3. Capture baseline runs with stock scheduler + EAS-capable setup.
4. Capture comparable runs under sched_ext candidates.
5. Compare medians (energy/runtime) and discuss placement behavior differences.

#### Practical host checks to include in your report/demo

Use checks like:

```bash
uname -a
cat /sys/devices/system/cpu/cpufreq/policy*/scaling_governor
ls /sys/devices/system/cpu/cpu*/cpu_capacity
```

If available on your kernel/debug build, include scheduler debug indicators related to energy-aware behavior as supplementary evidence.

#### If current machine is x86 desktop

1. Keep wording as: "energy-aware comparison framework" and "EAS-inspired direction".
2. Do not claim direct ARM-style EAS placement benefits were demonstrated.
3. Add a roadmap item: "Dedicated ARM heterogeneous validation phase for explicit EAS demonstration."

#### One-line presentation statement

- "Current results validate an energy-aware scheduling evaluation pipeline and sched_ext policy comparisons; explicit stock EAS behavior demonstration is planned on ARM heterogeneous hardware where EAS effects are most observable."

---

## 15. What to say in presentation (detailed speaking plan)

### 15.1 Start (problem + objective)

Say:

"Default scheduling is general-purpose. Our project targets energy-aware scheduling with dynamic quantum adjustment and validates decisions through robust repeated-trial benchmarking."

### 15.2 Explain implementation depth

Cover these concrete items:

1. CLI commands and their role.
2. FastAPI endpoints and async jobs.
3. Collector stack (runtime/system/RAPL/process/perf).
4. Scheduler adapters and cleanup safety.
5. SQLite persistence and cached median runs.
6. Dashboard visualization and live logs.

### 15.3 Explain methodology quality

1. Why medians over snapshots.
2. Why mixed workloads.
3. Why baseline-relative deltas.
4. How failures are counted and reported.

### 15.4 Present current result status

1. Mixed winners by workflow are expected.
2. bpfland appears strongest in median profile for target setup.
3. This validates direction, not final universal solution claim.

### 15.5 End with roadmap

1. Parameter sweep and ablation around dynamic quantum factors.
2. Implement custom sched_ext BPF scheduler approximating model policy.
3. Re-evaluate with the same median-board protocol for apples-to-apples evidence.

---

## 16. Claims, non-claims, and credibility rules

### 16.1 Safe claims

1. The project provides a complete and reproducible benchmark platform.
2. Real kernel scheduler switching experiments are operational.
3. Median-board methodology improves robustness versus single-run claims.
4. Some sched_ext candidates outperform baseline in specific conditions.

### 16.2 Unsafe claims

1. Any third-party scheduler is your custom scheduler.
2. Simulated model units are real hardware joules.
3. One scheduler universally dominates all workloads.

### 16.3 Credibility checklist before any demo

1. Show baseline and candidate with identical parameters.
2. Show trial count and median rationale.
3. State RAPL availability/permission status.
4. Distinguish model results from real-kernel results.
5. Mention reproducibility controls (governor/background load).

---

## 17. Suggested slide structure (practical)

1. Title and objective.
2. Problem and motivation.
3. System architecture.
4. Workload design.
5. Scheduler modes (default/simulated/sched_ext).
6. Metric collection pipeline.
7. Median methodology.
8. Aggregate results.
9. Workflow-level variability.
10. Why bpfland is current practical lead.
11. Limits and strict non-claims.
12. Roadmap to custom BPF scheduler.

---

## 18. Example concise final statement

"Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment is currently implemented as a two-layer engineering system: a validated algorithm model and a validated real-kernel sched_ext experimentation pipeline. Using repeated-trial median analysis with real energy and runtime metrics, we identify practical candidate policies such as bpfland while building directly toward our next milestone: a custom sched_ext BPF scheduler that implements our dynamic-quantum concept end-to-end."

---

## 19. Exact quick commands you can show live

```bash
uv venv
uv sync
uv run energy-scheduler doctor
uv run energy-scheduler workloads
uv run energy-scheduler run --scheduler linux_default --workload cpu_bound --tasks 2 --task-seconds 0.05
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler bpfland --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat
uv run energy-scheduler median-board --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --trials 5 --json
uv run energy-scheduler results --limit 20 --sort-by created_at --sort-order desc
uv run energy-scheduler serve --host 127.0.0.1 --port 8000
```

---

## 20. Final note for your viva/defense

If someone says, "This is just comparing existing schedulers," answer:

1. We implemented the full research-to-engineering pipeline ourselves (workloads, runner, collectors, storage, API, dashboard, async jobs, caching).
2. We validated both model and real-kernel tracks.
3. We generated robust decision evidence with repeated-trial median methodology.
4. This pipeline is exactly what is required to implement and verify a custom scheduler rigorously, and that is the next direct step.
