# Scheduler Behavior and Energy Analysis

## Scope and Ground Truth

This document explains how each scheduler behaved in this project benchmark flow,
why those outcomes differ, and how to classify each scheduler by energy-awareness
and dynamic quantum (slice) behavior.

Benchmark context used in this analysis:

- workload: `mixed_realistic`
- common run shape: `--tasks 8 --task-seconds 0.5 --repetitions 3`
- comparison mode: median leaderboard across repeated trials
- energy source: RAPL package joules (`rapl.package_energy_j`)

Important framing:

- `linux_default` and `custom_sched_ext` results are real kernel execution.
- `custom_simulated` is a model of our proposed algorithm, not kernel scheduler replacement.
- third-party sched_ext schedulers (cake/lavd/bpfland/etc.) are not our scheduler implementation.

## What We Measure and Why Winners Change

The leaderboard ranks by median package joules, but scheduler behavior also affects runtime.
Since energy is approximately power × time, a scheduler can reduce instantaneous power and still
consume more total joules if completion time increases enough.

Main causes of different winners across runs/workloads:

1. Different optimization goals per scheduler (latency vs locality vs fairness vs battery bias).
2. Different CPU topology behavior (migration/cache locality decisions).
3. Frequency-governor interaction (`schedutil` and load shape).
4. Short-run noise (thermal state, background processes).
5. Mixed workload composition (compression, file scan, local request bursts).

## Scheduler Classification Matrix

| Scheduler | Primary Design Goal | Energy-aware by default? | Dynamic quantum/slice behavior? | Notes |
|---|---|---|---|---|
| linux_default | general Linux fairness/latency balance | indirect only | yes (kernel internal timeslice behavior) | baseline (`SCHED_OTHER`; CFS/EEVDF family behavior) |
| custom_simulated | our model policy | yes (model-level) | yes (model-level) | simulation only, not kernel switching |
| scx_beerland | third-party sched_ext policy | not explicitly | yes | workload-sensitive |
| scx_bpfland | interactive responsiveness (vruntime-style) | partially (has energy knobs, defaults not strict energy mode) | yes | supports throttle/domain/slice controls |
| scx_cake | DRR-like latency/throughput policy | partially (profiles/quantum can bias power) | yes | highly tunable, objective is not pure energy minimization |
| scx_cosmos | locality-preserving lightweight scheduler | partially (has power-related switches) | yes | defaults focus locality and responsive mode switching |
| scx_flash | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |
| scx_lavd | latency-criticality deadline-style policy | not explicitly | yes | often strong latency behavior, not explicitly energy-first |
| scx_pandemonium | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |
| scx_p2dq | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |
| scx_tickless | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |
| scx_rustland | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |
| scx_rusty | third-party sched_ext policy | not explicitly | yes | benchmark-dependent |

Interpretation:

- "Energy-aware by default" means explicit default policy objective is minimizing energy.
- Many schedulers can be made more energy-friendly via knobs, but are not inherently
  optimized for joules as first objective.

## Per-Scheduler Behavior Analysis in This Benchmark Family

### linux_default

Observed role:

- stable baseline under mixed workload.
- often not the absolute best energy, but generally predictable.

Why:

- broad fairness and latency balance, not single-objective energy minimization.

Use when:

- you need neutral baseline for comparisons and regressions.

### custom_simulated

Observed role:

- useful to reason about our algorithm mechanics and schedule-event behavior.

Why:

- it applies our dynamic quantum model directly to task specs.
- not constrained by kernel implementation details.

Use when:

- validating algorithm shape and policy ideas before implementing BPF scheduler.

### scx_bpfland

Observed role:

- often competitive in mixed workloads; can be among lower-energy candidates.

Why:

- interactive-oriented dispatch and dynamic slice behavior.
- defaults are balanced; explicit power knobs exist but are optional.

Energy-awareness detail:

- supports `--throttle-us` and `--primary-domain powersave`, but default settings do not force
  energy-first behavior.

### scx_cake

Observed role:

- can win or lose depending on workload and run variance.

Why:

- dispatch/quantum policy can favor responsiveness and fairness tradeoffs.
- objective is not purely minimizing joules.

Energy-awareness detail:

- can be tuned for lower-power-leaning behavior, but default is not guaranteed to minimize energy.

### scx_cosmos

Observed role:

- frequently strong in locality-sensitive cases; can show low energy medians in mixed scenarios.

Why:

- locality-preserving behavior can reduce migration/cache penalties.
- mode switching under busy thresholds can alter responsiveness vs locality tradeoff.

Energy-awareness detail:

- contains power-related options (for example, deferred wakeup choices and CPU/domain controls),
  but default objective is locality and scheduling efficiency rather than explicit joule minimization.

### scx_lavd

Observed role:

- often strong on latency-sensitive behavior; energy ranking varies.

Why:

- latency-critical deadline-like policy may improve interaction timing but can increase/redistribute
  CPU activity depending on workload shape.

Energy-awareness detail:

- not explicitly marketed as an energy-minimization scheduler.

### scx_beerland, scx_flash, scx_pandemonium, scx_p2dq, scx_tickless, scx_rustland, scx_rusty

Observed role:

- each can be a local winner under specific run conditions, but none should be assumed universally
  better on energy.

Why:

- each policy emphasizes different tradeoffs in dispatching, locality, fairness, and wakeup behavior.

Energy-awareness detail:

- treat as workload-dependent candidates unless explicit energy-oriented defaults are documented.

## Why a Previously Tuned bpfland Variant Could Underperform

The removed tuned variant used explicit slice/domain/throttle controls.
That can increase total joules when runtime inflation outweighs any power reduction.

Typical mechanism:

1. tuning reduces instantaneous power by throttling or slower-core preference.
2. total completion time increases.
3. total package joules rise if runtime inflation dominates.

So a tuned profile is not automatically better; it is profile and workload dependent.

## Claims We Can Make Safely

1. Different schedulers behave differently on the same mixed workload.
2. Median-based comparison is more reliable than single-run snapshots.
3. Some third-party sched_ext schedulers can beat baseline on energy in specific scenarios.
4. No third-party scheduler here should be labeled as our custom scheduler implementation.

## What Remains Before UI Work

Core backend status for UI phase:

1. CLI benchmark and median-board flows are functional.
2. API endpoints for run/compare/results/median-board and async jobs are present.
3. Progress logging and failure diagnostics are available for long median-board runs.
4. RAPL collection works with current host permissions.

Recommended final backend cleanup before UI (optional but useful):

1. Add a compact API schema specifically for leaderboard chart consumption.
2. Add a small endpoint or field for benchmark metadata (kernel/governor/scheduler list snapshot).
3. Add one reproducibility note in docs for CPU governor and background load control.

If you skip the optional items above, the backend is still sufficient to start UI work.

## Source Notes

Behavior and classification in this document are based on:

- observed benchmark outputs in this repository workflow
- scheduler help text and option semantics available via local `scx_* --help`
- Linux scheduler and sched_ext documentation references already listed in project docs
