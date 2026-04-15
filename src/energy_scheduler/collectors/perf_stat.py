from __future__ import annotations

import os
import shutil
import signal
import subprocess

from energy_scheduler.collectors.base import Collector
from energy_scheduler.models import CollectorReading


class PerfStatCollector(Collector):
    name = "perf_stat"

    def __init__(
        self,
        events: tuple[str, ...] = (
            "task-clock",
            "context-switches",
            "cpu-migrations",
            "page-faults",
            "cycles",
            "instructions",
        ),
    ) -> None:
        self._events = events
        self._process: subprocess.Popen[str] | None = None
        self._perf_path = ""

    def start(self) -> None:
        perf_path = shutil.which("perf")
        if perf_path is None:
            return
        self._perf_path = perf_path

        command = [
            perf_path,
            "stat",
            "-x",
            ",",
            "-e",
            ",".join(self._events),
            "-p",
            str(os.getpid()),
        ]
        try:
            self._process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except OSError:
            self._process = None

    def stop(self) -> CollectorReading:
        if not self._perf_path:
            return CollectorReading(
                collector_name=self.name,
                metrics={"available": 0, "reason": "perf command not found"},
            )

        if self._process is None:
            return CollectorReading(
                collector_name=self.name,
                metrics={"available": 0, "reason": "perf collector failed to start"},
            )

        stderr_text = ""
        try:
            self._process.send_signal(signal.SIGINT)
            _, stderr_text = self._process.communicate(timeout=5)
        except (subprocess.SubprocessError, ProcessLookupError):
            self._process.kill()
            _, stderr_text = self._process.communicate()

        metrics: dict[str, float | int | str] = {
            "available": 1,
            "path": self._perf_path,
        }
        parsed = self._parse_perf_stat(stderr_text)
        metrics.update(parsed)

        if not parsed:
            metrics["available"] = 0
            metrics["reason"] = "perf stat returned no parseable metrics"
            stripped = stderr_text.strip()
            if stripped:
                metrics["stderr"] = stripped

        return CollectorReading(collector_name=self.name, metrics=metrics)

    def _parse_perf_stat(self, stderr_text: str) -> dict[str, float | int | str]:
        parsed: dict[str, float | int | str] = {}
        for line in stderr_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue

            columns = line.split(",")
            if len(columns) < 3:
                continue

            value_raw = columns[0].strip()
            event_raw = columns[2].strip()
            if not event_raw:
                continue

            event_name = (
                event_raw.replace("-", "_")
                .replace(" ", "_")
                .replace(":", "_")
                .replace("/", "_")
                .replace(".", "_")
                .lower()
            )

            if value_raw in {"<not supported>", "<not counted>", ""}:
                parsed[f"{event_name}_status"] = value_raw or "unknown"
                continue

            normalized = value_raw.replace(" ", "")
            try:
                if "." in normalized:
                    value: float | int = float(normalized)
                else:
                    value = int(normalized)
            except ValueError:
                try:
                    value = float(normalized)
                except ValueError:
                    parsed[f"{event_name}_raw"] = value_raw
                    continue

            parsed[event_name] = value

        return parsed