from __future__ import annotations

from dataclasses import dataclass

from energy_scheduler.models import (
    ScheduleEvent,
    SimulatedSchedule,
    TaskSpec,
    TaskTiming,
    WorkloadExecution,
)
from energy_scheduler.schedulers.base import SchedulerAdapter


@dataclass(slots=True)
class _TaskState:
    spec: TaskSpec
    remaining_cpu_s: float
    first_start_s: float | None = None
    finish_s: float | None = None


class CustomSimulatedScheduler(SchedulerAdapter):
    name = "custom_simulated"

    def __init__(
        self,
        base_quantum_s: float = 0.012,
        overutilized_threshold: float = 0.8,
    ) -> None:
        self._base_quantum_s = base_quantum_s
        self._overutilized_threshold = overutilized_threshold

    def prepare(self) -> None:
        return None

    def cleanup(self) -> None:
        return None

    def simulate(
        self,
        *,
        workload_name: str,
        repetition: int,
        tasks: list[TaskSpec],
    ) -> SimulatedSchedule:
        states = [
            _TaskState(spec=task, remaining_cpu_s=max(task.cpu_time_s, 0.000_001))
            for task in tasks
        ]
        overutilized = self._is_overutilized(tasks)
        clock_s = 0.0
        events: list[ScheduleEvent] = []

        while any(state.remaining_cpu_s > 0 for state in states):
            ready_states = [state for state in states if state.remaining_cpu_s > 0]
            ready_states.sort(key=lambda state: self._ranking_key(state, overutilized))
            state = ready_states[0]

            quantum_s = self._compute_quantum_s(
                state.spec,
                state.remaining_cpu_s,
                overutilized=overutilized,
            )
            run_for_s = min(quantum_s, state.remaining_cpu_s)

            if state.first_start_s is None:
                state.first_start_s = clock_s

            started_at_s = clock_s
            clock_s += run_for_s
            state.remaining_cpu_s -= run_for_s

            if state.remaining_cpu_s <= 0:
                state.finish_s = clock_s

            events.append(
                ScheduleEvent(
                    task_id=state.spec.task_id,
                    started_at_s=started_at_s,
                    finished_at_s=clock_s,
                    quantum_s=quantum_s,
                    priority=state.spec.priority,
                    energy_factor=self._energy_factor(state.spec),
                )
            )

        task_timings = tuple(
            TaskTiming(
                task_id=state.spec.task_id,
                arrival_time_s=0.0,
                start_time_s=state.first_start_s or 0.0,
                finish_time_s=state.finish_s or clock_s,
            )
            for state in states
        )
        execution = WorkloadExecution(
            workload_name=workload_name,
            scheduler_name=self.name,
            repetition=repetition,
            task_timings=task_timings,
            started_at_s=0.0,
            finished_at_s=clock_s,
        )
        return SimulatedSchedule(
            execution=execution,
            events=tuple(events),
            total_context_switches=max(len(events) - 1, 0),
            estimated_energy_units=sum(
                (event.finished_at_s - event.started_at_s) * event.energy_factor
                for event in events
            ),
        )

    def _ranking_key(
        self,
        state: _TaskState,
        overutilized: bool,
    ) -> tuple[float, int, str]:
        if overutilized:
            # EAS-inspired guardrail: under high utilization, favor throughput/fairness.
            return (0.0, state.spec.priority, state.spec.task_id)

        energy_factor = self._energy_factor(state.spec)
        priority_factor = self._priority_factor(state.spec.priority)
        # EDP-style score: penalize high-energy tasks while still honoring priority.
        score = (energy_factor * energy_factor) / max(priority_factor, 0.001)
        return (score, state.spec.priority, state.spec.task_id)

    def _compute_quantum_s(
        self,
        task: TaskSpec,
        remaining_cpu_s: float,
        *,
        overutilized: bool,
    ) -> float:
        priority_factor = self._priority_factor(task.priority)
        behavior_factor = self._behavior_factor(task)
        energy_factor = 1.0 if overutilized else self._energy_factor(task)
        quantum_s = self._base_quantum_s * priority_factor * behavior_factor / energy_factor
        return max(0.003, min(quantum_s, remaining_cpu_s, 0.05))

    def _is_overutilized(self, tasks: list[TaskSpec]) -> bool:
        if not tasks:
            return False
        cpu_ratios = [self._cpu_ratio(task) for task in tasks]
        average_cpu_ratio = sum(cpu_ratios) / len(cpu_ratios)
        return average_cpu_ratio >= self._overutilized_threshold

    def _priority_factor(self, priority: int) -> float:
        clamped = min(max(priority, 80), 139)
        return 1.0 + ((139 - clamped) / 59)

    def _behavior_factor(self, task: TaskSpec) -> float:
        cpu_phases = [phase for phase in task.phases if phase.kind == "cpu"]
        sleep_phases = [phase for phase in task.phases if phase.kind == "sleep"]
        if not sleep_phases:
            return 0.85
        if len(cpu_phases) >= 3:
            return 1.2
        return 1.05

    def _energy_factor(self, task: TaskSpec) -> float:
        cpu_ratio = self._cpu_ratio(task)
        return 1.0 + cpu_ratio

    def _cpu_ratio(self, task: TaskSpec) -> float:
        cpu_time_s = max(task.cpu_time_s, 0.000_001)
        total_time_s = sum(phase.duration_s for phase in task.phases)
        return cpu_time_s / max(total_time_s, 0.000_001)
