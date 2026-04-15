from __future__ import annotations

import os
import time

from energy_scheduler.collectors.base import Collector
from energy_scheduler.models import CollectorReading


class RuntimeCollector(Collector):
    name = "runtime"

    def __init__(self) -> None:
        self._started_at_s = 0.0

    def start(self) -> None:
        self._started_at_s = time.perf_counter()

    def stop(self) -> CollectorReading:
        elapsed_s = time.perf_counter() - self._started_at_s
        return CollectorReading(
            collector_name=self.name,
            metrics={"elapsed_s": elapsed_s},
        )


class SystemInfoCollector(Collector):
    name = "system_info"

    def start(self) -> None:
        return None

    def stop(self) -> CollectorReading:
        loadavg = os.getloadavg()
        return CollectorReading(
            collector_name=self.name,
            metrics={
                "cpu_count": os.cpu_count() or 0,
                "loadavg_1m": loadavg[0],
                "loadavg_5m": loadavg[1],
                "loadavg_15m": loadavg[2],
            },
        )
