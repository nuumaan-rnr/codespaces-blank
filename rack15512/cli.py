"""Command line interface.

Usage:
    python -m rack15512 run model.json [--outdir out] [--first-order]
    python -m rack15512 example [--outdir out] [--master sections.csv]
    python -m rack15512 sections [--master sections.csv] [--role upright]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from . import io_json
from .analysis import run_all
from .builder import RackConfig, build_rack
from .checks.en15512 import all_ok, run_checks
from .library import SectionLibrary
from .model import RackModel
from .report import write_report
from .viewer import (plot_deformed, plot_diagram, plot_frame_elevation,
                     plot_model, plot_utilization)


def _run(model: RackModel, outdir: str) -> int:
    os.makedirs(outdir, exist_ok=True)
    print(f"Model '{model.name}': {len(model.nodes)} nodes, "
          f"{len(model.members)} members, "
          f"{len(model.combinations)} combinations")
    cases = run_all(model)
    checks = run_checks(model, cases)

    report = write_report(model, cases, checks)
    with open(os.path.join(outdir, "report.md"), "w") as f:
        f.write(report)

    plot_model(model, os.path.join(outdir, "model.png"))
    plot_frame_elevation(model, 0.0,
                         os.path.join(outdir, "frame_elevation.png"))
    plot_utilization(model, checks, os.path.join(outdir, "utilization.png"))
    for case in cases:
        if not case.converged:
            continue
        tag = case.name.replace(" ", "_").replace("(", "").replace(")", "")
        plot_deformed(model, case, path=os.path.join(outdir, f"deformed_{tag}.png"))
        plot_diagram(model, case, "Mz", os.path.join(outdir, f"moment_{tag}.png"))
        plot_diagram(model, case, "N", os.path.join(outdir, f"axial_{tag}.png"))

    ok = all_ok(checks)
    print(f"\n{'ALL CHECKS PASS' if ok else 'CHECK FAILURES - see report'}")
    print(f"Report and plots written to {outdir}/")
    return 0 if ok else 2


def _load_library(path: str | None) -> SectionLibrary:
    return SectionLibrary.from_file(path) if path else SectionLibrary.bundled()


def _example_config(master_path: str | None) -> RackConfig:
    if master_path and master_path.lower().endswith((".xlsx", ".xlsm")):
        from .master_xlsx import load_master
        return RackConfig(master=load_master(master_path),
                          base_stiffness="auto")
    return RackConfig(library=_load_library(master_path))


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rack15512",
                                description="EN 15512 storage-rack analysis "
                                            "and design checks (OpenSees, 3D)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="analyse a model JSON file")
    pr.add_argument("model")
    pr.add_argument("--outdir", default="out")
    pr.add_argument("--first-order", action="store_true",
                    help="force linear analysis (default: second order)")

    pe = sub.add_parser("example", help="generate, save and run the demo rack")
    pe.add_argument("--outdir", default="out")
    pe.add_argument("--master", help="section master CSV/JSON/XLSX "
                                     "(default: bundled example master)")

    ps = sub.add_parser("sections", help="list the section master")
    ps.add_argument("--master", help="section master CSV/JSON/XLSX")
    ps.add_argument("--role", help="filter by role (upright/beam/bracing/...)")

    pf = sub.add_parser("rfem", help="import an RFEM data export, analyse it "
                                     "and (optionally) compare results")
    pf.add_argument("data", help="RFEM export .xlsx (1.1 Nodes, 1.7 Members, ...)")
    pf.add_argument("--master", help="section master .xlsx; recovers the "
                                     "load-dependent base springs that RFEM "
                                     "does not export")
    pf.add_argument("--fy", type=float, default=250.0,
                    help="design yield strength [MPa] (default 250)")
    pf.add_argument("--outdir", default="out_rfem")
    pf.add_argument("--compare", action="store_true",
                    help="compare member forces against the export's "
                         "'CO - 4.1' result sheets (validation.md)")
    pf.add_argument("--save-json", help="also save the imported model as JSON")

    a = p.parse_args(argv)
    if a.cmd == "run":
        model = io_json.load(a.model)
        if a.first_order:
            model.analysis.order = 1
        return _run(model, a.outdir)
    if a.cmd == "example":
        model = build_rack(_example_config(a.master))
        os.makedirs(a.outdir, exist_ok=True)
        io_json.save(model, os.path.join(a.outdir, "example_model.json"))
        return _run(model, a.outdir)
    if a.cmd == "rfem":
        from .master_xlsx import load_master
        from .rfem_import import load_rfem
        master = load_master(a.master) if a.master else None
        model = load_rfem(a.data, fy=a.fy, master=master)
        os.makedirs(a.outdir, exist_ok=True)
        if a.save_json:
            io_json.save(model, a.save_json)
        if not a.compare:
            return _run(model, a.outdir)
        from .analysis import run_all as _run_all
        from .rfem_compare import (compare_results, read_rfem_results,
                                   summarize)
        cases = _run_all(model)
        checks = run_checks(model, cases)
        with open(os.path.join(a.outdir, "report.md"), "w") as f:
            f.write(write_report(model, cases, checks))
        rfem_ref = read_rfem_results(a.data)
        comps = compare_results(model, cases, rfem_ref)
        with open(os.path.join(a.outdir, "validation.md"), "w") as f:
            f.write(summarize(comps))
        plot_model(model, os.path.join(a.outdir, "model.png"))
        plot_utilization(model, checks, os.path.join(a.outdir, "utilization.png"))
        print(f"Validation written to {a.outdir}/validation.md")
        return 0
    if a.cmd == "sections":
        lib = _load_library(a.master)
        for name in lib.names(a.role):
            s = lib.get(name)
            print(f"{s.name:20s} {s.role:10s} A={s.A:8.0f} Iy={s.Iy:.3e} "
                  f"Iz={s.Iz:.3e} J={s.J:.3e}  {s.description}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
