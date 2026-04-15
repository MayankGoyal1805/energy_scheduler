
# Operations Checklist

The dashboard UI and backend both use strict parameter-based caching. For stable results, set CPU governor to `performance` and minimize background load.

This file is the exact command plan to finish backend validation and unblock real energy measurements.

## A) Run now (no sudo)

1) Confirm current blocker

uv run energy-scheduler doctor --json
ls -l /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj

2) Backend smoke checks

uv run energy-scheduler run --scheduler linux_default --workload cpu_bound --tasks 1 --task-seconds 0.01
uv run energy-scheduler run --scheduler custom_simulated --workload mixed --tasks 2 --task-seconds 0.01
uv run energy-scheduler run --scheduler custom_sched_ext --sched-ext-scheduler cake --workload cpu_bound --tasks 1 --task-seconds 0.01
uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler cake --workload cpu_bound --tasks 1 --task-seconds 0.01 --json

3) API smoke checks

uv run energy-scheduler serve --host 127.0.0.1 --port 8000
curl -s http://127.0.0.1:8000/health
curl -s http://127.0.0.1:8000/workloads

## B) Run once on host with sudo (RAPL permission fix)

Note: user is already in group power in this machine output. The previous udev rule using MODE/GROUP alone does not update the energy_uj sysfs attribute permissions in this environment.

sudo groupadd -f power
sudo usermod -aG power "$USER"

sudo sh -c 'for f in /sys/class/powercap/intel-rapl:*/energy_uj; do chgrp power "$f" && chmod 0440 "$f"; done'
ls -l /sys/class/powercap/intel-rapl:0/energy_uj
cat /sys/class/powercap/intel-rapl:0/energy_uj
uv run energy-scheduler doctor --json

# If the manual command above works, make it persistent with a udev-triggered helper.
cat <<'EOF' | sudo tee /usr/local/sbin/fix-rapl-perms.sh
#!/usr/bin/env bash
set -euo pipefail
for f in /sys/class/powercap/intel-rapl:*/energy_uj; do
	[ -e "$f" ] || continue
	chgrp power "$f"
	chmod 0440 "$f"
done
EOF
sudo chmod 0755 /usr/local/sbin/fix-rapl-perms.sh

echo 'ACTION=="add|change", SUBSYSTEM=="powercap", KERNEL=="intel-rapl:*", RUN+="/usr/local/sbin/fix-rapl-perms.sh"' | sudo tee /etc/udev/rules.d/99-intel-rapl.rules
sudo udevadm control --reload-rules
sudo udevadm trigger --subsystem-match=powercap

# If manual chmod/chgrp fails with "Operation not permitted", kernel policy is enforcing root-only reads.
# In that case, collect RAPL as root (or adjust host kernel/security policy) and keep non-root runs for other metrics.

If you were newly added to group power in this session, log out and log back in.
If you were already in group power, no relogin is required after chmod/chgrp succeeds.

## C) Verify RAPL after relogin

id
ls -l /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
cat /sys/class/powercap/intel-rapl/intel-rapl:0/energy_uj
uv run energy-scheduler doctor --json

Expected: doctor rapl check becomes ok.

## D) Save evidence runs

uv run energy-scheduler compare --candidate-scheduler custom_sched_ext --sched-ext-scheduler cake --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save
uv run energy-scheduler results --limit 20 --sort-by created_at --sort-order desc --json

# Optional: sweep installed sched_ext schedulers and keep lower-energy candidates.
uv run energy-scheduler search-energy --workload mixed_realistic --tasks 8 --task-seconds 0.5 --repetitions 3 --perf-stat --save

## E) Optional API async flow check

uv run energy-scheduler serve --host 127.0.0.1 --port 8000
curl -s -X POST http://127.0.0.1:8000/jobs/compare -H 'content-type: application/json' -d '{"workload":"mixed_realistic","tasks":8,"task_seconds":0.5,"repetitions":3,"candidate_scheduler":"custom_sched_ext","sched_ext_scheduler":"cake","perf_stat":true,"save":true}'
curl -s http://127.0.0.1:8000/jobs/<job_id>
