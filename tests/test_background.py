import queue
import threading
import time

from pcb_alignment.background import BackgroundTasks, drain_latest


def wait_for_result(tasks: BackgroundTasks, task_id: int):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        for message in drain_latest(tasks.messages):
            if message.task_id == task_id and message.phase in {"result", "error"}:
                return message
        time.sleep(0.01)
    raise AssertionError("Background task did not finish")


def test_background_task_returns_result_and_progress() -> None:
    tasks = BackgroundTasks()
    try:
        task_id = tasks.submit("test", lambda report: (report("working", 0.5), 42)[1])
        message = wait_for_result(tasks, task_id)
        assert message.phase == "result"
        assert message.result == 42
    finally:
        tasks.shutdown()


def test_background_exception_is_delivered_to_queue() -> None:
    tasks = BackgroundTasks()
    try:
        def fail(report):
            raise RuntimeError("expected failure")

        task_id = tasks.submit("test", fail)
        message = wait_for_result(tasks, task_id)
        assert message.phase == "error"
        assert isinstance(message.error, RuntimeError)
        assert message.status == "expected failure"
    finally:
        tasks.shutdown()


def test_new_task_invalidates_old_result() -> None:
    tasks = BackgroundTasks()
    release = threading.Event()
    old_started = threading.Event()
    old_finished = threading.Event()
    try:
        def old(report):
            report("started", 0.1)
            old_started.set()
            release.wait(2)
            old_finished.set()
            report("cancel check", 0.5)
            return "old"

        old_id = tasks.submit("old", old)
        assert old_started.wait(1)
        new_id = tasks.submit("new", lambda report: "new")
        release.set()
        assert wait_for_result(tasks, new_id).result == "new"
        assert old_finished.wait(1)
        assert all(message.task_id != old_id for message in drain_latest(tasks.messages))
    finally:
        release.set()
        tasks.shutdown()
