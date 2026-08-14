"""Entry point for rack15512.background_run's subprocess worker - invoked as

    python -m rack15512._bg_worker <config_dir> <project_root> <master_root>
        <project_id> <system_id> <config_id> <plots:0|1> <label> <target>

A dedicated `-m` module (not multiprocessing.Process) so the child gets a
genuinely fresh interpreter with no connection to whatever script launched
the parent - see background_run.py's module docstring for why that matters
when the parent is a running Streamlit app script.
"""

from __future__ import annotations

import sys


def main(argv=None) -> None:
    from .background_run import _run_worker
    argv = sys.argv[1:] if argv is None else argv
    (config_dir, project_root, master_root, project_id, system_id,
     config_id, plots, label, target) = argv
    _run_worker(config_dir, project_root, master_root, project_id, system_id,
               config_id, plots == "1", label, target)


if __name__ == "__main__":
    main()
