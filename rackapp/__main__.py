"""Command line interface.

    python -m rackapp run examples/rack_example.yaml --out out/
    python -m rackapp run examples/rack_example.yaml --engine rfem
"""

from __future__ import annotations

import argparse
import os
import sys

from .config import RackConfig
from .pipeline import run
from .report import to_json, to_markdown


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="rackapp",
        description="Storage rack second-order analysis + EN 15512 checks",
    )
    sub = parser.add_subparsers(dest="cmd", required=True)
    p_run = sub.add_parser("run", help="run analysis and checks")
    p_run.add_argument("config", help="YAML input file")
    p_run.add_argument("--engine", choices=["internal", "rfem"],
                       help="override the engine from the config")
    p_run.add_argument("--out", default="out", help="output directory")
    p_run.add_argument("--no-plots", action="store_true")
    args = parser.parse_args(argv)

    cfg = RackConfig.from_yaml(args.config)
    if args.engine:
        cfg.analysis.engine = args.engine

    out = run(cfg)
    os.makedirs(args.out, exist_ok=True)

    md = to_markdown(cfg, out.model, out.results, out.report)
    with open(os.path.join(args.out, "report.md"), "w", encoding="utf-8") as f:
        f.write(md)
    with open(os.path.join(args.out, "results.json"), "w", encoding="utf-8") as f:
        f.write(to_json(cfg, out.model, out.results, out.report))

    if not args.no_plots:
        from .viz import plot_deformed, plot_model, plot_utilization
        plot_model(out.model).savefig(
            os.path.join(args.out, "model.png"), dpi=150, bbox_inches="tight")
        for cid, suffix in (("ULS_DA1", "deformed_down_aisle"),
                            ("ULS_CA", "deformed_cross_aisle")):
            combo = out.results.combos.get(cid)
            if combo:
                plot_deformed(out.model, combo).savefig(
                    os.path.join(args.out, f"{suffix}.png"),
                    dpi=150, bbox_inches="tight")
        plot_utilization(out.model, out.report).savefig(
            os.path.join(args.out, "utilization.png"), dpi=150, bbox_inches="tight")

    print(md)
    print(f"\nOutputs written to {args.out}/")
    return 0 if out.report.all_passed else 2


if __name__ == "__main__":
    sys.exit(main())
