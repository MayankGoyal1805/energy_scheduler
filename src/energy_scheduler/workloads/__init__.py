from energy_scheduler.workloads.base import Workload
from energy_scheduler.workloads.application import (
    CompressionWorkload,
    FileScanWorkload,
    LocalRequestBurstWorkload,
    MixedRealisticWorkload,
)
from energy_scheduler.workloads.synthetic import (
    BurstyPeriodicWorkload,
    CpuBoundWorkload,
    InteractiveShortWorkload,
    MixedWorkload,
)

__all__ = [
    "BurstyPeriodicWorkload",
    "CompressionWorkload",
    "CpuBoundWorkload",
    "FileScanWorkload",
    "InteractiveShortWorkload",
    "LocalRequestBurstWorkload",
    "MixedWorkload",
    "MixedRealisticWorkload",
    "Workload",
]
