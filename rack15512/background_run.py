"""Run a stored configuration in a separate OS process so a Streamlit rerun
(triggered by any click) never cancels an in-flight OpenSees analysis.

OpenSeesPy holds solver state as bare module-level globals within one process
(see engine/opensees.py) - safe across separate OS processes, unsafe across
threads sharing one process (see ui.run_cancellable_poll's docstring for why
a threaded runner was already tried and rejected for OpenSees work).

The run is launched as a genuinely fresh `python -m rack15512._bg_worker`
subprocess, NOT a multiprocessing.Process(spawn) - deliberately. Python's
multiprocessing spawn context always replays the parent's __main__ module in
the child (multiprocessing.spawn._fixup_main_from_path) to reconstruct any
state that might have been defined there; under real Streamlit, the parent's
__main__ IS app_streamlit.py itself (run via runpy, not import), which has
no __main__ guard - the replay would re-execute the whole app script (hero
UI, PSTORE/session routing, ...) outside any Streamlit runtime and crash
immediately. A `-m` subprocess has its own clean __main__ with no connection
to whatever launched the parent, so this never comes up.

Progress and completion are written to a JSON status file inside the
configuration's own directory (`_run_status.json`), atomically (temp file +
os.replace), so polling works from any browser session and survives a page
refresh - it isn't tied to the session_state of whoever started the run.
Cancellation is a small flag file for the same reason (so Stop works even if
a different session/tab requests it, or the one that started the run is
gone) rather than an in-memory object shared with the child.
"""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
import tempfile
import time
from typing import Optional

# Run function, as an importable "module:attr" path rather than a direct
# reference, so it can be named on the subprocess command line and so tests
# can point it at a fast fake instead of a real OpenSees run.
_DEFAULT_TARGET = "rack15512.project_run:run_configuration"


def _resolve(target: str):
    mod_name, func_name = target.split(":")
    return getattr(importlib.import_module(mod_name), func_name)


def _status_path(config_dir: str) -> str:
    return os.path.join(config_dir, "_run_status.json")


def _cancel_flag_path(config_dir: str) -> str:
    return os.path.join(config_dir, "_run_cancel.flag")


def _write_status(config_dir: str, data: dict) -> None:
    os.makedirs(config_dir, exist_ok=True)
    path = _status_path(config_dir)
    fd, tmp = tempfile.mkstemp(dir=config_dir, prefix=".run_status_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f)
        os.replace(tmp, path)
    except Exception:
        if os.path.exists(tmp):
            os.remove(tmp)
        raise


def poll_status(config_dir: str) -> Optional[dict]:
    """Current run status for a configuration, or None if no run has ever
    been started for it (or its status file has been cleared)."""
    try:
        with open(_status_path(config_dir), encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return None


def _run_worker(config_dir, project_root, master_root, project_id, system_id,
                config_id, plots, label, target):
    """Runs inside the `python -m rack15512._bg_worker` subprocess."""
    from .analysis import RunCancelled
    from .project import ProjectStore

    start = time.time()
    run_fn = _resolve(target)
    cancel_flag = _cancel_flag_path(config_dir)

    def should_cancel():
        return os.path.exists(cancel_flag)

    def cb(stage, frac):
        _write_status(config_dir, {
            "done": False, "error": None, "cancelled": False,
            "stage": stage, "frac": min(max(frac, 0.0), 1.0),
            "elapsed": time.time() - start, "label": label})

    store = ProjectStore(project_root)
    try:
        summary, _ = run_fn(
            store, project_id, system_id, config_id, plots=plots,
            master_root=master_root, progress=cb, should_cancel=should_cancel)
    except RunCancelled:
        _write_status(config_dir, {
            "done": True, "error": None, "cancelled": True,
            "stage": "Cancelled", "frac": 1.0,
            "elapsed": time.time() - start, "label": label})
    except Exception as exc:
        import traceback
        _write_status(config_dir, {
            "done": True, "error": str(exc), "cancelled": False,
            "stage": "Failed", "frac": 1.0,
            "elapsed": time.time() - start, "label": label,
            "error_type": type(exc).__name__,
            "traceback": traceback.format_exc()})
    else:
        _write_status(config_dir, {
            "done": True, "error": None, "cancelled": False,
            "stage": "Complete", "frac": 1.0,
            "elapsed": time.time() - start, "label": label,
            "summary": summary})
    finally:
        try:
            os.remove(cancel_flag)
        except OSError:
            pass


def start_run(project_root: str, master_root: str, project_id: str,
              system_id: str, config_id: str, *, plots: bool = True,
              label: str = "OpenSees second-order analysis",
              target: str = _DEFAULT_TARGET) -> str:
    """Start a background run for this configuration, or attach to one
    already in progress (started by this or another browser session).
    Returns the config_dir - the key poll_status()/request_cancel() take.

    target: "module:function" path to a run_configuration-shaped callable
    (store, project_id, system_id, config_id, *, plots, master_root,
    progress, should_cancel) -> (summary, cdir) - overridable so tests can
    point it at a fast fake instead of a real OpenSees run."""
    from .project import ProjectStore
    config_dir = ProjectStore(project_root).config_dir(
        project_id, system_id, config_id)
    existing = poll_status(config_dir)
    if existing is not None and not existing.get("done", True):
        return config_dir                      # already running - attach
    os.makedirs(config_dir, exist_ok=True)
    try:
        os.remove(_cancel_flag_path(config_dir))    # clear any stale flag
    except OSError:
        pass
    _write_status(config_dir, {"done": False, "error": None,
                              "cancelled": False, "stage": "Starting…",
                              "frac": 0.0, "elapsed": 0.0, "label": label})
    subprocess.Popen(
        [sys.executable, "-m", "rack15512._bg_worker", config_dir,
         project_root, master_root, project_id, system_id, config_id,
         "1" if plots else "0", label, target],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL, close_fds=True)
    return config_dir


def request_cancel(config_dir: str) -> bool:
    """Signal the running process for this config to stop after its current
    step.  Works regardless of which session/tab started the run (the flag
    is on disk, not in memory) - returns False if nothing is running."""
    status = poll_status(config_dir)
    if status is None or status.get("done", True):
        return False
    open(_cancel_flag_path(config_dir), "w", encoding="utf-8").close()
    return True
