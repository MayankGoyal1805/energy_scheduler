from __future__ import annotations

from abc import ABC, abstractmethod

from energy_scheduler.models import TaskSpec, WorkloadExecution


class Workload(ABC):
    name: str

    @abstractmethod
    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        raise NotImplementedError

    @abstractmethod
    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        raise NotImplementedError
