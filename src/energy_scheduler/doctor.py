from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True, frozen=True)
class DoctorCheck:
    name: str
    status: str
    detail: str

    def to_dict(self) -> dict[str, str]:
        return {
            "name": self.name,
            "status": self.status,
            "detail": self.detail,
        }


@dataclass(slots=True, frozen=True)
class DoctorReport:
    checks: tuple[DoctorCheck, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"checks": [check.to_dict() for check in self.checks]}


def run_doctor() -> DoctorReport:
    checks = [
        _kernel_check(),
        _sched_ext_sysfs_check(),
        _sched_ext_state_check(),
        _tool_check("scxctl"),
        _tool_check("bpftool"),
        _tool_check("perf"),
        _scxctl_list_check(),
        _rapl_readability_check(),
    ]
    return DoctorReport(checks=tuple(checks))


def format_doctor_report(report: DoctorReport) -> str:
    rows = [("check", "status", "detail")]
    rows.extend((check.name, check.status, check.detail) for check in report.checks)
    widths = [max(len(row[column]) for row in rows) for column in range(3)]
    lines = []
    for index, row in enumerate(rows):
        lines.append(
            "  ".join(value.ljust(widths[column]) for column, value in enumerate(row))
        )
        if index == 0:
            lines.append("  ".join("-" * width for width in widths))
    return "\n".join(lines)


def _kernel_check() -> DoctorCheck:
    completed = _run(["uname", "-r"])
    if completed.returncode == 0:
        return DoctorCheck("kernel", "ok", completed.stdout.strip())
    return DoctorCheck("kernel", "error", completed.stderr.strip() or "uname failed")


def _sched_ext_sysfs_check() -> DoctorCheck:
    path = Path("/sys/kernel/sched_ext")
    if path.exists():
        return DoctorCheck("sched_ext_sysfs", "ok", str(path))
    return DoctorCheck("sched_ext_sysfs", "missing", "no /sys/kernel/sched_ext")


def _sched_ext_state_check() -> DoctorCheck:
    state_path = Path("/sys/kernel/sched_ext/state")
    if not state_path.exists():
        return DoctorCheck("sched_ext_state", "missing", "state file not found")
    try:
        state = state_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        return DoctorCheck("sched_ext_state", "error", str(error))
    return DoctorCheck("sched_ext_state", "ok", state)


def _tool_check(command: str) -> DoctorCheck:
    path = shutil.which(command)
    if path is None:
        return DoctorCheck(command, "missing", f"{command} not found in PATH")
    return DoctorCheck(command, "ok", path)


def _scxctl_list_check() -> DoctorCheck:
    if shutil.which("scxctl") is None:
        return DoctorCheck("scxctl_list", "missing", "scxctl not found")
    completed = _run(["scxctl", "list"])
    if completed.returncode != 0:
        detail = completed.stderr.strip() or completed.stdout.strip() or "scxctl list failed"
        return DoctorCheck("scxctl_list", "error", detail)
    return DoctorCheck("scxctl_list", "ok", completed.stdout.strip())


def _rapl_readability_check() -> DoctorCheck:
    powercap_root = Path("/sys/class/powercap")
    energy_paths = sorted(powercap_root.glob("intel-rapl*/**/energy_uj"))
    if not energy_paths:
        return DoctorCheck("rapl", "missing", "no intel-rapl energy_uj files found")
    first_path = energy_paths[0]
    try:
        first_path.read_text(encoding="utf-8").strip()
    except OSError as error:
        return DoctorCheck("rapl", "error", f"cannot read {first_path}: {error}")
    return DoctorCheck("rapl", "ok", f"readable: {first_path}")


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            check=False,
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as error:
        return subprocess.CompletedProcess(
            args=command,
            returncode=1,
            stdout="",
            stderr=str(error),
        )
