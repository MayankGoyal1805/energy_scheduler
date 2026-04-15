from __future__ import annotations

import resource

from energy_scheduler.collectors.base import Collector
from energy_scheduler.models import CollectorReading


class ChildProcessUsageCollector(Collector):
    name = "child_process_usage"

    def __init__(self) -> None:
        self._start_usage: resource.struct_rusage | None = None

    def start(self) -> None:
        self._start_usage = resource.getrusage(resource.RUSAGE_CHILDREN)

    def stop(self) -> CollectorReading:
        if self._start_usage is None:
            return CollectorReading(
                collector_name=self.name,
                metrics={"available": 0, "reason": "collector was not started"},
            )

        end_usage = resource.getrusage(resource.RUSAGE_CHILDREN)
        start_usage = self._start_usage
        return CollectorReading(
            collector_name=self.name,
            metrics={
                "available": 1,
                "user_cpu_time_s": end_usage.ru_utime - start_usage.ru_utime,
                "system_cpu_time_s": end_usage.ru_stime - start_usage.ru_stime,
                "minor_page_faults": end_usage.ru_minflt - start_usage.ru_minflt,
                "major_page_faults": end_usage.ru_majflt - start_usage.ru_majflt,
                "voluntary_context_switches": end_usage.ru_nvcsw - start_usage.ru_nvcsw,
                "involuntary_context_switches": end_usage.ru_nivcsw - start_usage.ru_nivcsw,
            },
        )
