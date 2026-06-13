"""Run a stored configuration end-to-end and write its artifacts into the
project directory, recording a run summary against the configuration."""

from __future__ import annotations

import os
from typing import Optional, Tuple

from .analysis import run_all
from .builder import build_rack
from .checks.en15512 import run_checks
from .io_json import save as save_model
from .master_xlsx import load_master
from .project import Configuration, ProjectStore, summarize_run
from .report import write_report
from .viewer import (plot_deformed, plot_frame_elevation, plot_model,
                     plot_utilization)


def run_configuration(store: ProjectStore, project_id: str, system_id: str,
                      config_id: str, *, plots: bool = True) -> Tuple[dict, str]:
    """Build, analyse and check a stored configuration; write report and
    plots into its config directory; record and return the run summary.
    Returns (summary, config_dir)."""
    project = store.load(project_id)
    system = project.system(system_id)
    if system is None:
        raise KeyError(f"system '{system_id}' not found")
    conf = system.configuration(config_id)
    if conf is None:
        raise KeyError(f"configuration '{config_id}' not found")

    master = load_master(conf.master_path) \
        if conf.master_path and conf.master_path.lower().endswith(
            (".xlsx", ".xlsm")) else None
    library = None
    if conf.master_path and not master:
        from .library import SectionLibrary
        library = SectionLibrary.from_file(conf.master_path)
    cfg = conf.to_rackconfig(master=master, library=library)

    model = build_rack(cfg)
    cases = run_all(model)
    checks = run_checks(model, cases)

    cdir = store.config_dir(project_id, system_id, config_id)
    os.makedirs(cdir, exist_ok=True)
    save_model(model, os.path.join(cdir, "model.json"))
    with open(os.path.join(cdir, "report.md"), "w") as f:
        f.write(_project_header(project, system, conf) +
                write_report(model, cases, checks))
    if plots:
        plot_model(model, os.path.join(cdir, "model.png"))
        plot_frame_elevation(model, 0.0,
                             os.path.join(cdir, "frame_elevation.png"))
        plot_utilization(model, checks, os.path.join(cdir, "utilization.png"))
        for case in cases:
            if case.converged and case.kind == "ULS":
                plot_deformed(model, case,
                              path=os.path.join(cdir, "deformed.png"))
                break

    summary = summarize_run(model, cases, checks)
    store.update_run_summary(project_id, system_id, config_id, summary)
    return summary, cdir


def _project_header(project, system, conf: Configuration) -> str:
    lines = [
        f"# {project.name} - {system.name} - {conf.name}",
        "",
        f"- Project: **{project.name}**"
        + (f" (client: {project.client})" if project.client else ""),
        f"- Location: {project.location}" if project.location else "",
        f"- Engineer: {project.engineer}" if project.engineer else "",
        f"- Standard: {project.standard}",
        f"- System: {system.name}"
        + (f" - {system.description}" if system.description else ""),
        f"- Configuration: {conf.name}"
        + (f" - {conf.notes}" if conf.notes else ""),
        "",
        "---",
        "",
    ]
    return "\n".join(x for x in lines if x is not None) + "\n"
