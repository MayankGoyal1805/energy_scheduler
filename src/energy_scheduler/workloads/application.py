from __future__ import annotations

import hashlib
import json
import lzma
import multiprocessing as mp
import queue
import socket
import tempfile
import threading
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from energy_scheduler.models import TaskPhase, TaskSpec, TaskTiming, WorkloadExecution
from energy_scheduler.workloads.base import Workload


@dataclass(slots=True, frozen=True)
class _WorkerMessage:
    event: str
    task_id: str
    timestamp_s: float


@dataclass(slots=True, frozen=True)
class _CompressionJob:
    task: TaskSpec
    payload_bytes: int
    rounds: int


@dataclass(slots=True, frozen=True)
class _FileScanJob:
    task: TaskSpec
    root_dir: str
    rounds: int


@dataclass(slots=True, frozen=True)
class _RequestJob:
    task: TaskSpec
    url: str
    request_count: int
    pause_s: float


@dataclass(slots=True, frozen=True)
class _MixedJob:
    task: TaskSpec
    kind: str
    payload_bytes: int = 0
    rounds: int = 0
    root_dir: str = ""
    url: str = ""
    request_count: int = 0
    pause_s: float = 0.0


def _collect_execution(
    *,
    task_specs: list[TaskSpec],
    processes: list[mp.Process],
    start_gate: object,
    queue: mp.Queue,
    workload_name: str,
    scheduler_name: str,
    repetition: int,
) -> WorkloadExecution:
    for process in processes:
        process.start()

    started_at_s = time.perf_counter()
    start_gate.set()
    arrival_time_s = started_at_s

    messages: dict[str, dict[str, float]] = {
        task.task_id: {"arrival": arrival_time_s} for task in task_specs
    }
    expected_messages = len(task_specs) * 2
    received_messages = 0
    deadline_s = started_at_s + 120.0

    try:
        while received_messages < expected_messages:
            now_s = time.perf_counter()
            if now_s >= deadline_s:
                raise RuntimeError("timed out waiting for workload worker messages")

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
                        "workload workers exited before reporting completion: " + ", ".join(failed)
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
        for task in task_specs
    )
    return WorkloadExecution(
        workload_name=workload_name,
        scheduler_name=scheduler_name,
        repetition=repetition,
        task_timings=task_timings,
        started_at_s=started_at_s,
        finished_at_s=finished_at_s,
    )


def _compression_worker(job: _CompressionJob, start_gate: object, queue: mp.Queue) -> None:
    start_gate.wait()
    queue.put(_WorkerMessage("start", job.task.task_id, time.perf_counter()))
    try:
        payload = (f"{job.task.task_id}-payload-".encode("utf-8")) * max(job.payload_bytes // 20, 1)
        for _ in range(job.rounds):
            compressed = lzma.compress(payload, preset=6)
            hashlib.sha256(compressed).hexdigest()
            payload = compressed[: max(1024, len(compressed) // 2)] + payload[:1024]
    finally:
        queue.put(_WorkerMessage("finish", job.task.task_id, time.perf_counter()))


def _file_scan_worker(job: _FileScanJob, start_gate: object, queue: mp.Queue) -> None:
    start_gate.wait()
    queue.put(_WorkerMessage("start", job.task.task_id, time.perf_counter()))
    try:
        root = Path(job.root_dir)
        for _ in range(job.rounds):
            for file_path in sorted(root.rglob("*.txt")):
                digest = hashlib.sha256()
                with file_path.open("rb") as handle:
                    digest.update(handle.read())
                digest.hexdigest()
    finally:
        queue.put(_WorkerMessage("finish", job.task.task_id, time.perf_counter()))


def _request_worker(job: _RequestJob, start_gate: object, queue: mp.Queue) -> None:
    start_gate.wait()
    queue.put(_WorkerMessage("start", job.task.task_id, time.perf_counter()))
    try:
        for _ in range(job.request_count):
            try:
                with urllib.request.urlopen(job.url, timeout=2) as response:
                    response.read()
            except Exception:
                pass
            time.sleep(job.pause_s)
    finally:
        queue.put(_WorkerMessage("finish", job.task.task_id, time.perf_counter()))


def _mixed_worker(job: _MixedJob, start_gate: object, queue: mp.Queue) -> None:
    start_gate.wait()
    queue.put(_WorkerMessage("start", job.task.task_id, time.perf_counter()))
    try:
        if job.kind == "compression":
            payload = (f"{job.task.task_id}-payload-".encode("utf-8")) * max(job.payload_bytes // 20, 1)
            for _ in range(job.rounds):
                compressed = lzma.compress(payload, preset=6)
                hashlib.sha256(compressed).hexdigest()
                payload = compressed[: max(1024, len(compressed) // 2)] + payload[:1024]
        elif job.kind == "file_scan":
            root = Path(job.root_dir)
            for _ in range(job.rounds):
                for file_path in sorted(root.rglob("*.txt")):
                    digest = hashlib.sha256()
                    with file_path.open("rb") as handle:
                        digest.update(handle.read())
                    digest.hexdigest()
        elif job.kind == "request":
            for _ in range(job.request_count):
                try:
                    with urllib.request.urlopen(job.url, timeout=2) as response:
                        response.read()
                except Exception:
                    pass
                time.sleep(job.pause_s)
        else:
            raise ValueError(f"unsupported mixed workload kind: {job.kind}")
    finally:
        queue.put(_WorkerMessage("finish", job.task.task_id, time.perf_counter()))


class _JsonHandler(BaseHTTPRequestHandler):
    server_version = "EnergySchedulerTestServer/0.1"

    def do_GET(self) -> None:  # noqa: N802
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        seed = params.get("seed", ["0"])[0]
        payload = {
            "path": parsed.path,
            "seed": seed,
            "checksum": hashlib.sha256(seed.encode("utf-8")).hexdigest(),
        }
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:
        return None


def _stop_test_server(server: ThreadingHTTPServer, server_thread: threading.Thread) -> None:
    """Best-effort server shutdown that never blocks benchmark teardown forever."""
    if server_thread.is_alive():
        shutdown_thread = threading.Thread(target=server.shutdown, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(timeout=2)

    try:
        server.server_close()
    except OSError:
        pass

    server_thread.join(timeout=2)


class ApplicationWorkload(Workload):
    name = "application"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        raise NotImplementedError


class CompressionWorkload(ApplicationWorkload):
    name = "compression"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id=f"compression-{index}",
                priority=120 - index,
                phases=(TaskPhase(kind="cpu", duration_s=task_seconds),),
            )
            for index in range(task_count)
        ]

    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        tasks = self.build_tasks(task_count, task_seconds)
        payload_bytes = max(64_000, int(task_seconds * 512_000))
        rounds = max(2, int(task_seconds * 10))
        jobs = [
            _CompressionJob(task=task, payload_bytes=payload_bytes, rounds=rounds)
            for task in tasks
        ]
        ctx = mp.get_context("spawn")
        start_gate = ctx.Event()
        queue: mp.Queue[_WorkerMessage] = ctx.Queue()
        processes = [
            ctx.Process(target=_compression_worker, args=(job, start_gate, queue), daemon=False)
            for job in jobs
        ]
        return _collect_execution(
            task_specs=tasks,
            processes=processes,
            start_gate=start_gate,
            queue=queue,
            workload_name=self.name,
            scheduler_name=scheduler_name,
            repetition=repetition,
        )


class FileScanWorkload(ApplicationWorkload):
    name = "file_scan"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id=f"file-scan-{index}",
                priority=110 - index,
                phases=(
                    TaskPhase(kind="cpu", duration_s=task_seconds / 2),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 8),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 2),
                ),
            )
            for index in range(task_count)
        ]

    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        tasks = self.build_tasks(task_count, task_seconds)
        rounds = max(1, int(task_seconds * 4))
        files_per_task = max(8, int(task_seconds * 24))
        with tempfile.TemporaryDirectory(prefix="energy-scheduler-scan-") as temp_dir:
            task_roots = _build_scan_fixture(
                root=Path(temp_dir),
                task_specs=tasks,
                files_per_task=files_per_task,
            )
            jobs = [
                _FileScanJob(task=task, root_dir=str(task_roots[task.task_id]), rounds=rounds)
                for task in tasks
            ]
            ctx = mp.get_context("spawn")
            start_gate = ctx.Event()
            queue: mp.Queue[_WorkerMessage] = ctx.Queue()
            processes = [
                ctx.Process(target=_file_scan_worker, args=(job, start_gate, queue), daemon=False)
                for job in jobs
            ]
            return _collect_execution(
                task_specs=tasks,
                processes=processes,
                start_gate=start_gate,
                queue=queue,
                workload_name=self.name,
                scheduler_name=scheduler_name,
                repetition=repetition,
            )


class LocalRequestBurstWorkload(ApplicationWorkload):
    name = "local_request_burst"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        return [
            TaskSpec(
                task_id=f"request-{index}",
                priority=100 - index,
                phases=(
                    TaskPhase(kind="cpu", duration_s=task_seconds / 5),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 10),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 5),
                ),
            )
            for index in range(task_count)
        ]

    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        tasks = self.build_tasks(task_count, task_seconds)
        request_count = max(4, int(task_seconds * 24))
        pause_s = max(0.005, task_seconds / 20)
        server = ThreadingHTTPServer(("127.0.0.1", 0), _JsonHandler)
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        try:
            jobs = [
                _RequestJob(
                    task=task,
                    url=f"http://127.0.0.1:{server.server_port}/work?seed={task.task_id}",
                    request_count=request_count,
                    pause_s=pause_s,
                )
                for task in tasks
            ]
            ctx = mp.get_context("spawn")
            start_gate = ctx.Event()
            queue: mp.Queue[_WorkerMessage] = ctx.Queue()
            processes = [
                ctx.Process(target=_request_worker, args=(job, start_gate, queue), daemon=False)
                for job in jobs
            ]
            return _collect_execution(
                task_specs=tasks,
                processes=processes,
                start_gate=start_gate,
                queue=queue,
                workload_name=self.name,
                scheduler_name=scheduler_name,
                repetition=repetition,
            )
        finally:
            _stop_test_server(server, server_thread)


class MixedRealisticWorkload(ApplicationWorkload):
    name = "mixed_realistic"

    def build_tasks(self, task_count: int, task_seconds: float) -> list[TaskSpec]:
        tasks: list[TaskSpec] = []
        for index in range(task_count):
            if index % 3 == 0:
                phases = (TaskPhase(kind="cpu", duration_s=task_seconds),)
            elif index % 3 == 1:
                phases = (
                    TaskPhase(kind="cpu", duration_s=task_seconds / 3),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 8),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 3),
                )
            else:
                phases = (
                    TaskPhase(kind="cpu", duration_s=task_seconds / 5),
                    TaskPhase(kind="sleep", duration_s=task_seconds / 10),
                    TaskPhase(kind="cpu", duration_s=task_seconds / 5),
                )
            tasks.append(
                TaskSpec(
                    task_id=f"mixed-real-{index}",
                    priority=115 - index,
                    phases=phases,
                )
            )
        return tasks

    def execute(
        self,
        scheduler_name: str,
        repetition: int,
        task_count: int,
        task_seconds: float,
    ) -> WorkloadExecution:
        tasks = self.build_tasks(task_count, task_seconds)
        payload_bytes = max(64_000, int(task_seconds * 512_000))
        compression_rounds = max(2, int(task_seconds * 8))
        scan_rounds = max(1, int(task_seconds * 3))
        files_per_task = max(6, int(task_seconds * 18))
        request_count = max(4, int(task_seconds * 20))
        pause_s = max(0.005, task_seconds / 20)

        server = ThreadingHTTPServer(("127.0.0.1", 0), _JsonHandler)
        server.daemon_threads = True
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()

        with tempfile.TemporaryDirectory(prefix="energy-scheduler-mixed-") as temp_dir:
            scan_tasks = [task for index, task in enumerate(tasks) if index % 3 == 1]
            task_roots = _build_scan_fixture(
                root=Path(temp_dir),
                task_specs=scan_tasks,
                files_per_task=files_per_task,
            )
            jobs: list[_MixedJob] = []
            for index, task in enumerate(tasks):
                if index % 3 == 0:
                    jobs.append(
                        _MixedJob(
                            task=task,
                            kind="compression",
                            payload_bytes=payload_bytes,
                            rounds=compression_rounds,
                        )
                    )
                elif index % 3 == 1:
                    jobs.append(
                        _MixedJob(
                            task=task,
                            kind="file_scan",
                            root_dir=str(task_roots[task.task_id]),
                            rounds=scan_rounds,
                        )
                    )
                else:
                    jobs.append(
                        _MixedJob(
                            task=task,
                            kind="request",
                            url=f"http://127.0.0.1:{server.server_port}/work?seed={task.task_id}",
                            request_count=request_count,
                            pause_s=pause_s,
                        )
                    )

            ctx = mp.get_context("spawn")
            start_gate = ctx.Event()
            queue: mp.Queue[_WorkerMessage] = ctx.Queue()
            processes = [
                ctx.Process(target=_mixed_worker, args=(job, start_gate, queue), daemon=False)
                for job in jobs
            ]
            try:
                return _collect_execution(
                    task_specs=tasks,
                    processes=processes,
                    start_gate=start_gate,
                    queue=queue,
                    workload_name=self.name,
                    scheduler_name=scheduler_name,
                    repetition=repetition,
                )
            finally:
                _stop_test_server(server, server_thread)


def _build_scan_fixture(
    *,
    root: Path,
    task_specs: list[TaskSpec],
    files_per_task: int,
) -> dict[str, Path]:
    task_roots: dict[str, Path] = {}
    for task in task_specs:
        task_dir = root / task.task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        for index in range(files_per_task):
            content = (
                f"{task.task_id}:{index}:"
                + hashlib.sha256(f"{task.task_id}-{index}".encode("utf-8")).hexdigest()
            )
            (task_dir / f"sample-{index}.txt").write_text(content * 16, encoding="utf-8")
        task_roots[task.task_id] = task_dir
    return task_roots
