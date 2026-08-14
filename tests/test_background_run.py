"""Tests for the subprocess-backed background run runner.

Exercises rack15512.background_run against a tiny fake "run_configuration"-
shaped target (module-level, spawn-picklable by dotted path) instead of a
real OpenSees run, so these stay fast while still covering the real
subprocess boundary: status-file plumbing, cancellation, and error surface."""

import os
import signal
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import background_run
from rack15512.analysis import RunCancelled


def _fake_run_configuration(store, project_id, system_id, config_id, *,
                            plots=True, master_root="masters", progress=None,
                            should_cancel=None):
    cdir = store.config_dir(project_id, system_id, config_id)
    for i, frac in enumerate([0.2, 0.5, 0.8]):
        if progress:
            progress(f"fake stage {i}", frac)
        time.sleep(0.05)
    return {"verdict": "PASS", "note": "fake"}, cdir


def _fake_run_configuration_slow(store, project_id, system_id, config_id, *,
                                 plots=True, master_root="masters",
                                 progress=None, should_cancel=None):
    cdir = store.config_dir(project_id, system_id, config_id)
    for i in range(100):
        if should_cancel and should_cancel():
            raise RunCancelled("cancelled")
        if progress:
            progress(f"waiting {i}", i / 100)
        time.sleep(0.05)
    return {"verdict": "PASS"}, cdir


def _fake_run_configuration_fails(store, project_id, system_id, config_id, *,
                                  plots=True, master_root="masters",
                                  progress=None, should_cancel=None):
    if progress:
        progress("about to fail", 0.1)
    raise ValueError("synthetic failure")


def _wait_done(cdir, timeout=30.0):
    deadline = time.time() + timeout
    status = None
    while time.time() < deadline:
        status = background_run.poll_status(cdir)
        if status and status.get("done"):
            return status
        time.sleep(0.1)
    raise AssertionError(f"run did not finish within {timeout}s "
                         f"(last status: {status})")


def test_start_run_completes_and_writes_status(tmp_path):
    root = str(tmp_path / "projects")
    cdir = background_run.start_run(
        root, "masters", "p1", "s1", "c1",
        target="tests.test_background_run:_fake_run_configuration")
    status = _wait_done(cdir)
    assert status["error"] is None
    assert status["cancelled"] is False
    assert status["summary"]["verdict"] == "PASS"
    assert status["frac"] == 1.0


def test_poll_status_none_when_never_started(tmp_path):
    assert background_run.poll_status(str(tmp_path / "nope")) is None


def test_start_run_dedups_while_in_progress(tmp_path):
    root = str(tmp_path / "projects")
    target = "tests.test_background_run:_fake_run_configuration_slow"
    cdir1 = background_run.start_run(root, "masters", "p2", "s1", "c1",
                                     target=target)
    cdir2 = background_run.start_run(root, "masters", "p2", "s1", "c1",
                                     target=target)
    assert cdir1 == cdir2
    status = background_run.poll_status(cdir1)
    assert status["done"] is False
    background_run.request_cancel(cdir1)
    _wait_done(cdir1)


def test_request_cancel_stops_the_run(tmp_path):
    root = str(tmp_path / "projects")
    cdir = background_run.start_run(
        root, "masters", "p3", "s1", "c1",
        target="tests.test_background_run:_fake_run_configuration_slow")
    for _ in range(50):                          # wait until it's actually running
        status = background_run.poll_status(cdir)
        if status and status.get("frac", 0.0) > 0.0:
            break
        time.sleep(0.05)
    assert background_run.request_cancel(cdir) is True
    status = _wait_done(cdir)
    assert status["cancelled"] is True
    assert status["error"] is None


def test_request_cancel_unknown_run_returns_false():
    assert background_run.request_cancel("/no/such/config/dir") is False


def test_failed_run_reports_error_type(tmp_path):
    root = str(tmp_path / "projects")
    cdir = background_run.start_run(
        root, "masters", "p4", "s1", "c1",
        target="tests.test_background_run:_fake_run_configuration_fails")
    status = _wait_done(cdir)
    assert status["error_type"] == "ValueError"
    assert "synthetic failure" in status["error"]
    assert status["cancelled"] is False


def test_killed_worker_reported_as_crash_not_frozen_forever(tmp_path):
    """A worker that's killed outright (OOM, native-code fault, ...) skips
    every except clause in _run_worker and never writes a final status - the
    UI must not just poll a frozen "not done" status forever with no
    feedback; poll_status() should notice the process is gone and surface a
    clear error itself."""
    root = str(tmp_path / "projects")
    cdir = background_run.start_run(
        root, "masters", "p6", "s1", "c1",
        target="tests.test_background_run:_fake_run_configuration_slow")
    pid = None
    for _ in range(50):
        status = background_run.poll_status(cdir)
        if status and status.get("pid") and status.get("frac", 0.0) > 0.0:
            pid = status["pid"]
            break
        time.sleep(0.05)
    assert pid, "worker never reported a pid / made progress"
    os.kill(pid, signal.SIGKILL)

    status = None
    deadline = time.time() + 10.0
    while time.time() < deadline:
        status = background_run.poll_status(cdir)
        if status and status.get("done"):
            break
        time.sleep(0.1)
    assert status["done"] is True
    assert status["cancelled"] is False
    assert status["error_type"] == "WorkerProcessDied"
    assert status["stage"] != "Complete"
