"""Command line interface.

Usage:
    python -m rack15512 run model.json [--outdir out] [--first-order]
    python -m rack15512 example [--outdir out]   # build + run the demo rack
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
from .model import RackModel
from .report import write_report
from .viewer import plot_deformed, plot_diagram, plot_model, plot_utilization


def _run(model: RackModel, outdir: str) -> int:
    os.makedirs(outdir, exist_ok=True)
    print(f"Model '{model.name}': {len(model.nodes)} nodes, "
          f"{len(model.members)} members, "
          f"{len(model.combinations)} combinations")
    cases = run_all(model)
    checks = run_checks(model, cases)

    report = write_report(model, cases, checks)
    rpath = os.path.join(outdir, "report.md")
    with open(rpath, "w") as f:
        f.write(report)

    plot_model(model, os.path.join(outdir, "model.png"))
    plot_utilization(model, checks, os.path.join(outdir, "utilization.png"))
    for case in cases:
        if not case.converged:
            continue
        tag = case.name.replace(" ", "_").replace("(", "").replace(")", "")
        plot_deformed(model, case, path=os.path.join(outdir, f"deformed_{tag}.png"))
        plot_diagram(model, case, "M", os.path.join(outdir, f"moment_{tag}.png"))
        plot_diagram(model, case, "N", os.path.join(outdir, f"axial_{tag}.png"))

    ok = all_ok(checks)
    print(f"\n{'ALL CHECKS PASS' if ok else 'CHECK FAILURES - see report'}")
    print(f"Report and plots written to {outdir}/")
    return 0 if ok else 2


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rack15512",
                                description="EN 15512 storage-rack analysis "
                                            "and design checks (OpenSees)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="analyse a model JSON file")
    pr.add_argument("model")
    pr.add_argument("--outdir", default="out")
    pr.add_argument("--first-order", action="store_true",
                    help="force linear analysis (default: second order)")

    pe = sub.add_parser("example", help="generate, save and run the demo rack")
    pe.add_argument("--outdir", default="out")

    a = p.parse_args(argv)
    if a.cmd == "run":
        model = io_json.load(a.model)
        if a.first_order:
            model.analysis.order = 1
        return _run(model, a.outdir)
    if a.cmd == "example":
        model = build_rack(RackConfig())
        os.makedirs(a.outdir, exist_ok=True)
        io_json.save(model, os.path.join(a.outdir, "example_model.json"))
        return _run(model, a.outdir)
    return 1


if __name__ == "__main__":
    sys.exit(main())
