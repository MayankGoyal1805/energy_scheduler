from __future__ import annotations

from dataclasses import asdict, dataclass, field
from statistics import mean
from typing import Any, Literal
from uuid import uuid4

SchedulerMode = Literal["linux_default", "custom_sched_ext", "custom_simulated"]
PhaseKind = Literal["cpu", "sleep"]


@dataclass(slots=True, frozen=True)
class TaskPhase:
    kind: PhaseKind
    duration_s: float


@dataclass(slots=True, frozen=True)
class TaskSpec:
    task_id: str
    priority: int
    phases: tuple[TaskPhase, ...]

    @property
    def cpu_time_s(self) -> float:
        return sum(phase.duration_s for phase in self.phases if phase.kind == "cpu")


@dataclass(slots=True, frozen=True)
class TaskTiming:
    task_id: str
    arrival_time_s: float
    start_time_s: float
    finish_time_s: float

    @property
    def waiting_time_s(self) -> float:
        return self.start_time_s - self.arrival_time_s

    @property
    def turnaround_time_s(self) -> float:
        return self.finish_time_s - self.arrival_time_s

    @property
    def response_time_s(self) -> float:
        return self.waiting_time_s


@dataclass(slots=True, frozen=True)
class WorkloadExecution:
    workload_name: str
    scheduler_name: str
    repetition: int
    task_timings: tuple[TaskTiming, ...]
    started_at_s: float
    finished_at_s: float

    @property
    def runtime_s(self) -> float:
        return self.finished_at_s - self.started_at_s

    @property
    def average_waiting_time_s(self) -> float:
        return mean(task.waiting_time_s for task in self.task_timings)

    @property
    def average_turnaround_time_s(self) -> float:
        return mean(task.turnaround_time_s for task in self.task_timings)

    @property
    def average_response_time_s(self) -> float:
        return mean(task.response_time_s for task in self.task_timings)


@dataclass(slots=True, frozen=True)
class CollectorReading:
    collector_name: str
    metrics: dict[str, float | int | str]


@dataclass(slots=True, frozen=True)
class ScheduleEvent:
    task_id: str
    started_at_s: float
    finished_at_s: float
    quantum_s: float
    priority: int
    energy_factor: float


@dataclass(slots=True, frozen=True)
class SimulatedSchedule:
    execution: WorkloadExecution
    events: tuple[ScheduleEvent, ...]
    total_context_switches: int
    estimated_energy_units: float


@dataclass(slots=True, frozen=True)
class BenchmarkRun:
    run_id: str
    workload_name: str
    scheduler_name: str
    task_count: int
    task_seconds: float
    repetitions: int
    executions: tuple[WorkloadExecution, ...]
    collector_readings: tuple[CollectorReading, ...] = field(default_factory=tuple)
    schedule_events: tuple[ScheduleEvent, ...] = field(default_factory=tuple)
    notes: str = ""

    @classmethod
    def create(
        cls,
        workload_name: str,
        scheduler_name: str,
        task_count: int,
        task_seconds: float,
        repetitions: int,
        executions: tuple[WorkloadExecution, ...],
        collector_readings: tuple[CollectorReading, ...],
        schedule_events: tuple[ScheduleEvent, ...] = (),
        notes: str = "",
    ) -> "BenchmarkRun":
        return cls(
            run_id=str(uuid4()),
            workload_name=workload_name,
            scheduler_name=scheduler_name,
            task_count=task_count,
            task_seconds=task_seconds,
            repetitions=repetitions,
            executions=executions,
            collector_readings=collector_readings,
            schedule_events=schedule_events,
            notes=notes,
        )

    @property
    def average_runtime_s(self) -> float:
        return mean(execution.runtime_s for execution in self.executions)

    @property
    def average_waiting_time_s(self) -> float:
        return mean(execution.average_waiting_time_s for execution in self.executions)

    @property
    def average_turnaround_time_s(self) -> float:
        return mean(execution.average_turnaround_time_s for execution in self.executions)

    @property
    def average_response_time_s(self) -> float:
        return mean(execution.average_response_time_s for execution in self.executions)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["summary"] = {
            "average_runtime_s": self.average_runtime_s,
            "average_waiting_time_s": self.average_waiting_time_s,
            "average_turnaround_time_s": self.average_turnaround_time_s,
            "average_response_time_s": self.average_response_time_s,
        }
        return payload
