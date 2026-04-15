from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from energy_scheduler.collectors.base import Collector
from energy_scheduler.models import CollectorReading


class PerfInfoCollector(Collector):
    name = "perf_info"

    def start(self) -> None:
        return None

    def stop(self) -> CollectorReading:
        perf_path = shutil.which("perf")
        if perf_path is None:
            return CollectorReading(
                collector_name=self.name,
                metrics={"available": 0, "reason": "perf command not found"},
            )

        metrics: dict[str, float | int | str] = {
            "available": 1,
            "path": perf_path,
        }
        version = self._read_perf_version()
        if version:
            metrics["version"] = version

        paranoid_path = Path("/proc/sys/kernel/perf_event_paranoid")
        if paranoid_path.exists():
            metrics["perf_event_paranoid"] = paranoid_path.read_text(
                encoding="utf-8"
            ).strip()

        return CollectorReading(collector_name=self.name, metrics=metrics)

    def _read_perf_version(self) -> str:
        try:
            completed = subprocess.run(
                ["perf", "--version"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return ""
        return completed.stdout.strip() or completed.stderr.strip()
