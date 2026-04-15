from __future__ import annotations

from energy_scheduler.schedulers.base import SchedulerAdapter


class LinuxDefaultScheduler(SchedulerAdapter):
    name = "linux_default"

    def prepare(self) -> None:
        return None

    def cleanup(self) -> None:
        return None
