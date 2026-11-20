"""Thread-safe background task coordination for the Tkinter application."""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
import queue
import threading
from typing import Any, Callable, Generic, TypeVar


ResultT = TypeVar("ResultT")
StatusCallback = Callable[[str, float | None], None]
TaskFunction = Callable[[StatusCallback], ResultT]


class TaskCancelled(Exception):
    """Internal signal used to stop invalidated background work cooperatively."""


@dataclass(frozen=True)
class TaskMessage:
    task_id: int
    kind: str
    phase: str
    status: str = ""
    progress: float | None = None
    result: Any = None
    error: BaseException | None = None


class BackgroundTasks(Generic[ResultT]):
    """Run one operation at a time and publish results through a queue."""

    def __init__(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gcodealign")
        self._messages: queue.Queue[TaskMessage] = queue.Queue()
        self._lock = threading.Lock()
        self._generation = 0
        self._future: Future[Any] | None = None

    @property
    def messages(self) -> queue.Queue[TaskMessage]:
        return self._messages

    def submit(self, kind: str, operation: TaskFunction[ResultT]) -> int:
        with self._lock:
            self._generation += 1
            task_id = self._generation
            old_future = self._future
            if old_future is not None:
                old_future.cancel()
            self._future = self._executor.submit(self._run, task_id, kind, operation)
            return task_id

    def invalidate(self) -> None:
        with self._lock:
            self._generation += 1
            if self._future is not None:
                self._future.cancel()

    def _is_current(self, task_id: int) -> bool:
        with self._lock:
            return task_id == self._generation

    def _publish(self, message: TaskMessage) -> None:
        if self._is_current(message.task_id):
            self._messages.put_nowait(message)

    def _run(self, task_id: int, kind: str, operation: TaskFunction[ResultT]) -> None:
        def report(status: str, progress: float | None = None) -> None:
            if not self._is_current(task_id):
                raise TaskCancelled
            self._publish(TaskMessage(task_id, kind, "progress", status, progress))

        self._publish(TaskMessage(task_id, kind, "started"))
        try:
            result = operation(report)
        except TaskCancelled:
            return
        except Exception as error:
            self._publish(TaskMessage(task_id, kind, "error", str(error), error=error))
        else:
            self._publish(TaskMessage(task_id, kind, "result", result=result))

    def shutdown(self) -> None:
        self.invalidate()
        self._executor.shutdown(wait=False, cancel_futures=True)


def drain_latest(messages: queue.Queue[TaskMessage]) -> list[TaskMessage]:
    """Drain all currently available messages without blocking the caller."""
    drained: list[TaskMessage] = []
    while True:
        try:
            drained.append(messages.get_nowait())
        except queue.Empty:
            return drained
        else:
            messages.task_done()
