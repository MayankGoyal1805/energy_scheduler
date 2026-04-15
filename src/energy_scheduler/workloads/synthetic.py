from __future__ import annotations

import multiprocessing as mp
import queue
import time
from dataclasses import dataclass

from energy_scheduler.models import TaskPhase, TaskSpec, TaskTiming, WorkloadExecution
from energy_scheduler.workloads.base import Workload


@dataclass(slots=True, frozen=True)
class _WorkerMessage:
    event: str
    task_id: str
    timestamp_s: float


def _busy_loop(duration_s: float) -> None:
    deadline = time.perf_counter() + duration_s
    value = 0
    while time.perf_counter() < deadline:
        value += 1
    if value < 0:
        raise RuntimeError("unreachable guard to keep the loop alive")


def _worker(task: TaskSpec, start_gate: mp.synchronize.Event, queue: mp.Queue) -> None:
    start_gate.wait()
    queue.put(_WorkerMessage("start", task.task_id, time.perf_counter()))
    for phase in task.phases:
        if phase.kind == "cpu":
            _busy_loop(phase.duration_s)
        else:
            time.sleep(phase.duration_s)
    queue.put(_WorkerMessage("finish", task.task_id, time.perf_counter()))


class SyntheticWorkload(Workload):
    name = "synthetic"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        raise NotImplementedError

    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        tasks = self.build_tasks(task_count=task_count, task_seconds=task_seconds)
        ctx = mp.get_context("spawn")
        start_gate = ctx.Event()
        queue: mp.Queue[_WorkerMessage] = ctx.Queue()
        processes = [
            ctx.Process(target=_worker, args=(task, start_gate, queue), daemon=False)
            for task in tasks
        ]

        for process in processes:
            process.start()

        started_at_s = time.perf_counter()
        start_gate.set()
        arrival_time_s = started_at_s

        messages: dict[str, dict[str, float]] = {
            task.task_id: {"arrival": arrival_time_s} for task in tasks
        }
        expected_messages = len(tasks) * 2
        received_messages = 0
        deadline_s = started_at_s + 120.0

        try:
            while received_messages < expected_messages:
                now_s = time.perf_counter()
                if now_s >= deadline_s:
                    raise RuntimeError("timed out waiting for synthetic workload worker messages")

                try:
                    message = queue.get(timeout=min(1.0, deadline_s - now_s))
                except queue.Empty:
                    failed = [
                        f"{process.pid}:{process.exitcode}"
                        for process in processes
                        if process.exitcode not in (None, 0)
                    ]
                    if failed:
                        raise RuntimeError(
                            "synthetic workers exited before reporting completion: " + ", ".join(failed)
                        )
                    continue

                if message.task_id in messages:
                    messages[message.task_id][message.event] = message.timestamp_s
                    received_messages += 1
        finally:
            for process in processes:
                process.join(timeout=2)
            for process in processes:
                if process.is_alive():
                    process.terminate()
                    process.join(timeout=2)

        finished_at_s = max(task_data["finish"] for task_data in messages.values())
        task_timings = tuple(
            TaskTiming(
                task_id=task.task_id,
                arrival_time_s=messages[task.task_id]["arrival"],
                start_time_s=messages[task.task_id]["start"],
                finish_time_s=messages[task.task_id]["finish"],
            )
            for task in tasks
        )
        return WorkloadExecution(
            workload_name=self.name,
            scheduler_name=scheduler_name,
            repetition=repetition,
            task_timings=task_timings,
            started_at_s=started_at_s,
            finished_at_s=finished_at_s,
        )


class CpuBoundWorkload(SyntheticWorkload):
    name = "cpu_bound"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id=f"cpu-{index}",
                priority=120 - index,
                phases=(TaskPhase(kind="cpu", duration_s=task_seconds),),
            )
            for index in range(task_count)
        ]


class InteractiveShortWorkload(SyntheticWorkload):
    name = "interactive_short"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        cpu_slice = max(task_seconds / 4, 0.01)
        sleep_slice = max(task_seconds / 8, 0.005)
        return [
            TaskSpec(
                task_id=f"interactive-{index}",
                priority=100 - index,
                phases=(
                    TaskPhase(kind="cpu", duration_s=cpu_slice),
                    TaskPhase(kind="sleep", duration_s=sleep_slice),
                    TaskPhase(kind="cpu", duration_s=cpu_slice),
                ),
            )
            for index in range(task_count)
        ]


class MixedWorkload(SyntheticWorkload):
    name = "mixed"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        for index in range(task_count):
            if index % 3 == 0:
                phases = (
                    TaskPhase(kind="cpu", duration_s=task_seconds * 1.25),
                )
            elif index % 3 == 1:
                phases = (
                    TaskPhase(kind="cpu", duration_s=task_seconds / 2),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 4),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 2),
                )
            else:
                phases = (
                    TaskPhase(kind="cpu", duration_s=task_seconds / 3),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 3),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 3),
                )
            tasks.append(
                TaskSpec(
                    task_id=f"mixed-{index}",
                    priority=110 - index,
                    phases=phases,
                )
            )
        return tasks


class BurstyPeriodicWorkload(SyntheticWorkload):
    name = "bursty_periodic"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        cpu_slice = max(task_seconds / 5, 0.01)
        sleep_slice = max(task_seconds / 3, 0.01)
        return [
            TaskSpec(
                task_id=f"bursty-{index}",
                priority=115 - index,
                phases=(
                    TaskPhase(kind="cpu", duration_s=cpu_slice),
                    TaskPhase(kind="sleep", duration_s=sleep_slice),
                    TaskPhase(kind="cpu", duration_s=cpu_slice),
                    TaskPhase(kind="sleep", duration_s=sleep_slice),
                    TaskPhase(kind="cpu", duration_s=cpu_slice),
                ),
            )
            for index in range(task_count)
        ]
