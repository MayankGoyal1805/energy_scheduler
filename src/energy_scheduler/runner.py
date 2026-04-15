from __future__ import annotations

from energy_scheduler.collectors import (
    ChildProcessUsageCollector,
    PerfInfoCollector,
    PerfStatCollector,
    RaplCollector,
    RuntimeCollector,
    SystemInfoCollector,
)
from energy_scheduler.config import BenchmarkSettings
from energy_scheduler.models import BenchmarkRun, CollectorReading, ScheduleEvent
from energy_scheduler.schedulers import (
    CustomSimulatedScheduler,
    LinuxDefaultScheduler,
    SchedExtScheduler,
    SchedulerAdapter,
)
from energy_scheduler.workloads import (
    BurstyPeriodicWorkload,
    CompressionWorkload,
    CpuBoundWorkload,
    FileScanWorkload,
    InteractiveShortWorkload,
    LocalRequestBurstWorkload,
    MixedWorkload,
    MixedRealisticWorkload,
    Workload,
)


class BenchmarkRunner:
    def __init__(self) -> None:
        self._workloads: dict[str, Workload] = {
            workload.name: workload
            for workload in (
                CpuBoundWorkload(),
                InteractiveShortWorkload(),
                MixedWorkload(),
                BurstyPeriodicWorkload(),
                CompressionWorkload(),
                FileScanWorkload(),
                LocalRequestBurstWorkload(),
                MixedRealisticWorkload(),
            )
        }
        self._schedulers: dict[str, SchedulerAdapter] = {
            LinuxDefaultScheduler.name: LinuxDefaultScheduler(),
            CustomSimulatedScheduler.name: CustomSimulatedScheduler(),
        }

    def available_workloads(self) -> list[str]:
        return sorted(self._workloads)

    def run(self, settings: BenchmarkSettings) -> BenchmarkRun:
        workload = self._workloads[settings.workload_name]
        scheduler = self._build_scheduler(settings)

        scheduler.prepare()
        collector_readings: list[CollectorReading] = []
        collectors = [
            RuntimeCollector(),
            SystemInfoCollector(),
            RaplCollector(),
            ChildProcessUsageCollector(),
            PerfInfoCollector(),
        ]
        if settings.enable_perf_stat:
            collectors.append(PerfStatCollector())
        try:
            for collector in collectors:
                collector.start()

            schedule_events: tuple[ScheduleEvent, ...] = ()
            if isinstance(scheduler, CustomSimulatedScheduler):
                simulated_results = tuple(
                    scheduler.simulate(
                        workload_name=settings.workload_name,
                        repetition=repetition,
                        tasks=workload.build_tasks(
                            task_count=settings.task_count,
                            task_seconds=settings.task_seconds,
                        ),
                    )
                    for repetition in range(settings.repetitions)
                )
                executions = tuple(result.execution for result in simulated_results)
                schedule_events = tuple(
                    event
                    for result in simulated_results
                    for event in result.events
                )
                collector_readings.append(
                    CollectorReading(
                        collector_name="custom_simulated_scheduler",
                        metrics={
                            "available": 1,
                            "context_switches": sum(
                                result.total_context_switches
                                for result in simulated_results
                            ),
                            "estimated_energy_units": sum(
                                result.estimated_energy_units
                                for result in simulated_results
                            ),
                            "note": "relative model units, not joules",
                        },
                    )
                )
            else:
                executions = tuple(
                    workload.execute(
                        scheduler_name=settings.scheduler_name,
                        repetition=repetition,
                        task_count=settings.task_count,
                        task_seconds=settings.task_seconds,
                    )
                    for repetition in range(settings.repetitions)
                )
        finally:
            for collector in collectors:
                collector_readings.append(collector.stop())
            scheduler.cleanup()
            if isinstance(scheduler, SchedExtScheduler):
                collector_readings.append(
                    CollectorReading(
                        collector_name="custom_sched_ext",
                        metrics=scheduler.metadata(),
                    )
                )

        return BenchmarkRun.create(
            workload_name=settings.workload_name,
            scheduler_name=settings.scheduler_name,
            task_count=settings.task_count,
            task_seconds=settings.task_seconds,
            repetitions=settings.repetitions,
            executions=executions,
            collector_readings=tuple(collector_readings),
            schedule_events=schedule_events,
        )

    def _build_scheduler(self, settings: BenchmarkSettings) -> SchedulerAdapter:
        if settings.scheduler_name == SchedExtScheduler.name:
            return SchedExtScheduler(
                settings.sched_ext_scheduler,
                settings.sched_ext_args,
            )
        return self._schedulers[settings.scheduler_name]
