# Backend Runbook

This runbook is the end-to-end backend operations guide.

## 1. Environment Setup

```bash
uv venv
uv sync
```

Health check:

```bash
uv run energy-scheduler doctor
```

Expected for this machine right now:

- sched_ext checks: OK
- perf checks: OK
- RAPL readability: permission denied (known blocker)

## 2. Basic Benchmark Runs

Linux default run:

```bash
uv run energy-scheduler run --scheduler linux_default --workload cpu_bound --tasks 2 --task-seconds 0.05
```

Simulated policy run:

```bash
uv run energy-scheduler run --scheduler custom_simulated --workload mixed --tasks 4 --task-seconds 0.05
```

Real sched_ext run:

```bash
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler cake --workload cpu_bound --tasks 1 --task-seconds 0.02
```

## 3. Performance Counter Collection

Enable optional perf stat:

```bash
uv run energy-scheduler run --workload cpu_bound --perf-stat
uv run energy-scheduler compare --workload mixed --perf-stat
```

Notes:

- perf stat fields are parsed from CSV output
- if not supported/not counted, status fields are emitted instead

## 4. Scheduler Comparison Workflow

Default vs simulated:

```bash
uv run energy-scheduler compare --workload mixed --tasks 4 --task-seconds 0.05
```

Default vs real sched_ext:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat
```

Save comparison runs:

```bash
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
```

## 5. Results Inspection

List recent:

```bash
uv run energy-scheduler results --limit 20
```

Filter/sort:

```bash
uv run energy-scheduler results --scheduler custom_sched_ext --sort-by average_runtime_s --sort-order asc
```

Date-range:

```bash
uv run energy-scheduler results --from-time 2026-04-14T00:00:00 --to-time 2026-04-15T00:00:00
```

Run detail:

```bash
uv run energy-scheduler results --run-id <run_id>
```

## 6. API Operations

Start API server:

```bash
uv run energy-scheduler serve --host 127.0.0.1 --port 8000
```

Open docs:

```text
http://127.0.0.1:8000/docs
```

Sync API run:

```bash
curl -s -X POST http://127.0.0.1:8000/run \
  -H 'content-type: application/json' \
  -d '{"workload":"cpu_bound","tasks":2,"task_seconds":0.05,"perf_stat":true}' | jq .
```

Async compare job:

```bash
curl -s -X POST http://127.0.0.1:8000/jobs/compare \
  -H 'content-type: application/json' \
  -d '{"workload":"mixed_realistic","tasks":8,"task_seconds":0.5,"repetitions":3,"candidate_scheduler":"custom_sched_ext","sched_ext_scheduler":"lavd","perf_stat":true,"save":true}' | jq .
```

Poll job:

```bash
curl -s http://127.0.0.1:8000/jobs/<job_id> | jq .
```

## 7. Known Blockers and Fixes

### RAPL Permission Denied

Current state in this environment:

- `/sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj` is root-readable only

Host-side fix examples (run on real machine with sudo):

```bash
sudo groupadd -f power
sudo usermod -aG power "$USER"
echo 'SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", MODE="0440", GROUP="power"' | sudo tee /etc/udev/rules.d/99-intel-rapl.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=powercap
```

Then re-login and verify:

```bash
ls -l /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
uv run energy-scheduler doctor
```

### sched_ext Safety

- always use short test runs first
- keep cleanup path intact (`runner` uses `finally` cleanup)
- verify state after runs:

```bash
cat /sys/kernel/sched_ext/state
scxctl get
```

## 8. Ready-for-UI Contract

Backend now provides everything needed for UI integration:

- workload listing
- doctor status
- synchronous and asynchronous benchmark run/compare
- persisted result listing with filters and sort
- full run detail retrieval

Suggested frontend integration order:

1. workloads + doctor cards
2. run form + result panel
3. compare form + comparison table
4. results history view
5. async job polling UX for long runs
