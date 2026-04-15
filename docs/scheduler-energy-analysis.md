
# Scheduler Behavior and Energy Analysis

The dashboard UI leaderboard and comparison logic use only real schedulers as candidates. Simulated schedulers are for model/algorithm analysis only. For stable results, set CPU governor to `performance` and minimize background load.

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

## Current Status Snapshot

Current project state:

1. CLI benchmark, compare, search-energy, and median-board flows are functional.
2. API endpoints for run/compare/results/median-board and async jobs are present.
3. Dashboard UI is active and consumes the same backend logic.
4. Progress logging and failure diagnostics are available for long median-board runs.
5. RAPL collection is available when host permissions allow access.

Recommended next technical milestones:

1. Expand benchmark metadata capture (kernel/governor/background load snapshot) for stronger reproducibility reporting.
2. Run larger-trial median studies for tighter confidence in cross-workflow ranking.
3. Implement custom sched_ext BPF scheduler approximating dynamic-quantum policy and evaluate with the same protocol.

## Source Notes

Behavior and classification in this document are based on:

- observed benchmark outputs in this repository workflow
- scheduler help text and option semantics available via local `scx_* --help`
- Linux scheduler and sched_ext documentation references already listed in project docs

## How To Present This As "Your Project"

Use this framing consistently:

1. Project identity:
  - "Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment"
2. Engineering reality:
  - today we have two validated tracks:
    - algorithm track: `custom_simulated` (our policy model)
    - kernel track: `custom_sched_ext` (real Linux switching experiments)
3. Main contribution now:
  - a reproducible benchmark platform that measures energy/performance tradeoffs and identifies which real sched_ext policies best match our objective profile
4. Main contribution next:
  - convert validated policy insights into a custom BPF sched_ext implementation

This lets you claim a real, defensible project now without overclaiming custom-kernel completion.

## The Core Storyline (Use This In Demos)

Present in this exact sequence:

1. Problem:
  - default scheduling optimizes general fairness/latency, not explicit energy-delay goals for your mixed workload profile
2. Hypothesis:
  - dynamic quantum adjustment can improve energy-delay behavior by adapting slices to task behavior/intensity
3. Method:
  - evaluate across realistic mixed workloads using RAPL joules + runtime + variability-aware medians
4. Evidence:
  - no single scheduler wins every workload; median-based ranking reveals robust candidates under noise
5. Decision:
  - `scx_bpfland` is currently the best practical candidate for your objective in median scoring, while still acknowledging workflow-level variance
6. Roadmap:
  - tune/ablate bpfland-style controls, then implement custom sched_ext policy approximating your dynamic-quantum model

## How To Handle "Mixed Bag" Results (Important)

Do not present mixed results as failure. Present them as expected behavior in multi-objective systems.

Use this line:

- "In scheduler research, per-workload winners vary. Robustness comes from repeated-trial medians, variance tracking, and transparent tradeoff analysis, not single-run universal winners."

Then show why medians matter:

- outliers from thermal spikes/background load are de-emphasized
- central tendency across repeated trials is more stable
- scheduler selection becomes evidence-based, not anecdotal

## How To Position bpfland Specifically

Use this careful claim set:

1. What you can say:
  - `scx_bpfland` is currently the strongest practical candidate in your median leaderboard for the target benchmark profile
  - it exhibits dynamic slice behavior and tunable controls aligned with your project objective space
  - it does not win every workflow, but it offers the best robust median balance in current data
2. What you should not say:
  - "bpfland is universally best"
  - "bpfland is our custom scheduler"
3. Why this is still strong:
  - your project is about energy-aware dynamic scheduling methodology and implementation path, not only about naming one universal winner

Suggested sentence for slides:

- "Among tested real sched_ext policies, bpfland is our best median-score proxy for the project objective, and our custom policy implementation will build on these validated dynamics."

## What You Must Mention During Presentation (Detailed Checklist)

### 1) Objective Definition

- Primary: lower package energy (RAPL joules)
- Secondary: avoid unacceptable runtime regressions
- Tertiary: maintain robustness across mixed workloads

### 2) Experimental Controls

- fixed task/workload parameters per comparison
- repeated trials and median scoring
- same machine/kernel configuration
- documented candidate list and settings
- note whether `perf_stat` is enabled

### 3) Metrics and Their Meaning

- `median_energy_j`: primary energy outcome
- `median_runtime_s`: performance cost/benefit
- `median_delta_percent`: relative to baseline (`linux_default`)
- failed-trial count: operational reliability signal

### 4) Why Median Leaderboard Is The Right Primary View

- mitigates run-to-run noise
- better than best-case snapshots
- supports practical deployment decisions

### 5) Scheduler Interpretation Boundaries

- third-party sched_ext schedulers are comparative references
- `custom_simulated` is policy-model validation, not kernel proof
- real kernel proof requires custom BPF sched_ext policy implementation

### 6) Current Best Practical Outcome

- bpfland leads as median-score candidate in current benchmark profile
- winner variability across workflows is expected and explicitly tracked

### 7) Future Work (Concrete)

- parameter sweep around bpfland-like controls (slice/throttle/domain)
- ablation studies for dynamic-quantum factors
- implement custom sched_ext BPF scheduler approximating model policy
- validate against same median-board protocol

## Suggested Slide Deck Structure (10-12 Slides)

1. Title + problem statement
2. Why energy-aware scheduling matters (energy vs runtime tradeoff)
3. Architecture (model track + kernel track)
4. Methodology (workloads, trials, medians, metrics)
5. Candidate schedulers and classification matrix
6. Aggregate median results (energy/runtime)
7. Workflow-level variability view
8. Why bpfland is current best practical candidate
9. Limits and non-claims (strict honesty slide)
10. Roadmap to custom BPF implementation
11. Key takeaways
12. Q&A backup: metric definitions + reproducibility settings

## Ready-To-Use Talking Points

Opening:

- "This project delivers a reproducible platform for energy-aware scheduler evaluation and a validated path from policy model to real kernel implementation."

When asked "Why not one clear winner?":

- "Schedulers are multi-objective and workload-sensitive. Our decision criterion is robust median behavior across repeated trials, where bpfland currently leads for our target profile."

When asked "Is this your scheduler yet?":

- "Our algorithm is validated in simulation and our kernel pipeline is validated with sched_ext. The next milestone is custom BPF policy implementation using the same evaluation harness."

Closing:

- "The project already provides measurable, reproducible evidence and a concrete implementation roadmap; it is not just comparison, it is a full engineering pipeline from hypothesis to deployable kernel policy."

## Presentation Risk Management (What Can Hurt Credibility)

Avoid these mistakes:

1. Claiming universal winner status for any scheduler
2. Mixing simulated energy units with real joules
3. Ignoring variability/failed-trial counts
4. Presenting single-run screenshots as final evidence

Always include:

1. Baseline comparison against `linux_default`
2. Trial count and median rationale
3. Explicit distinction between model vs kernel execution
4. Reproducibility controls (governor/background load)

## Final Positioning Statement (Use Verbatim If Needed)

"Energy-Aware CPU Scheduling Algorithm with Dynamic Quantum Adjustment is currently a two-layer project: a validated algorithm layer (`custom_simulated`) and a validated real-kernel experimentation layer (`custom_sched_ext`). Using repeated-trial median evaluation with RAPL energy and runtime tradeoffs, bpfland is our strongest practical candidate in the present profile, and these results directly guide the next step: implementing our own sched_ext BPF scheduler with dynamic quantum adjustment."
