from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from energy_scheduler.schedulers.base import SchedulerAdapter


@dataclass(slots=True, frozen=True)
class ScxCommandResult:
    command: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str


class SchedExtScheduler(SchedulerAdapter):
    name = "custom_sched_ext"

    def __init__(
        self,
        scheduler_name: str = "cake",
        scheduler_args: str | None = None,
    ) -> None:
        self._scheduler_name = scheduler_name
        self._scheduler_args = scheduler_args
        self._started = False
        self._prepare_result: ScxCommandResult | None = None
        self._cleanup_result: ScxCommandResult | None = None

    @property
    def scheduler_name(self) -> str:
        return self._scheduler_name

    @property
    def prepare_result(self) -> ScxCommandResult | None:
        return self._prepare_result

    @property
    def cleanup_result(self) -> ScxCommandResult | None:
        return self._cleanup_result

    def prepare(self) -> None:
        self._require_sched_ext()
        command = ["scxctl", "start", "--sched", self._scheduler_name]
        if self._scheduler_args:
            command.append(f"--args={self._scheduler_args}")
        result = self._run_scxctl(command)

        # If a scheduler is already active, switch instead of failing the run.
        result_message = f"{result.stderr}\n{result.stdout}".lower()
        if result.returncode != 0 and "already running" in result_message:
            switch_command = ["scxctl", "switch", "--sched", self._scheduler_name]
            if self._scheduler_args:
                switch_command.append(f"--args={self._scheduler_args}")
            result = self._run_scxctl(switch_command)

        self._prepare_result = result
        if result.returncode != 0:
            raise RuntimeError(
                "failed to activate sched_ext scheduler "
                f"{self._scheduler_name}: {result.stderr or result.stdout}"
            )
        self._started = True

    def cleanup(self) -> None:
        if not self._started:
            return
        self._cleanup_result = self._run_scxctl(["scxctl", "stop"])
        self._started = False

    def metadata(self) -> dict[str, int | str]:
        metadata: dict[str, int | str] = {
            "available": 1,
            "sched_ext_scheduler": self._scheduler_name,
        }
        if self._scheduler_args:
            metadata["sched_ext_args"] = self._scheduler_args
        if self._prepare_result is not None:
            metadata["start_returncode"] = self._prepare_result.returncode
            metadata["start_stdout"] = self._prepare_result.stdout
            metadata["start_stderr"] = self._prepare_result.stderr
        if self._cleanup_result is not None:
            metadata["stop_returncode"] = self._cleanup_result.returncode
            metadata["stop_stdout"] = self._cleanup_result.stdout
            metadata["stop_stderr"] = self._cleanup_result.stderr
        return metadata

    def _require_sched_ext(self) -> None:
        if not Path("/sys/kernel/sched_ext").exists():
            raise RuntimeError("sched_ext sysfs path not found: /sys/kernel/sched_ext")

    def _run_scxctl(self, command: list[str]) -> ScxCommandResult:
        completed = subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=30,
        )
        return ScxCommandResult(
            command=tuple(command),
            returncode=completed.returncode,
            stdout=completed.stdout.strip(),
            stderr=completed.stderr.strip(),
        )
