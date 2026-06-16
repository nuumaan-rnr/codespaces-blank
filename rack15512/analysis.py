"""Runs all combinations: assembles factored loads, applies the EN 15512
sway imperfection (EHF or initial geometry, in the configured horizontal
directions), solves first and second order, and returns the analysis
cases."""

from __future__ import annotations

import os
import sys
from typing import List

from .combos import apply_ehf, assemble
from .engine.opensees import OpenSeesEngine
from .model import DIRECTION_VECTORS, RackModel
from .results import CaseResult


def run_all(model: RackModel, progress=None) -> List[CaseResult]:
    # set RACK_VERBOSE=1 to echo per-combination run remarks to the terminal
    # (otherwise remarks go only to the progress callback, e.g. the app UI)
    verbose = bool(os.environ.get("RACK_VERBOSE"))

    def step(stage, frac):
        if verbose:
            print(f"[rack] {frac * 100:4.0f}%  {stage}", file=sys.stderr,
                  flush=True)
        if progress:
            progress(stage, frac)

    errors = model.validate()
    if errors:
        raise ValueError("Model validation failed:\n  " + "\n  ".join(errors))

    engine = OpenSeesEngine()
    order = model.analysis.order
    results: List[CaseResult] = []

    n_combo = len(model.combinations) or 1
    for ci, combo in enumerate(model.combinations):
        step(f"Running {combo.kind} combination {combo.name}",
             0.30 + 0.14 * ci / n_combo)
        base_loads = assemble(model, combo)
        apply_imp = combo.imperfection and (combo.kind == "ULS"
                                            or combo.imp_directions)
        if apply_imp:
            directions = combo.imp_directions or model.imperfection.directions
        else:
            directions = [""]

        for direction in directions:
            loads = base_loads
            geom_sway = None
            name = combo.name
            if direction:
                phi = model.imperfection.value_for(direction)
                vec = DIRECTION_VECTORS[direction]
                if model.imperfection.method.upper() == "EHF":
                    loads = apply_ehf(model, base_loads, phi, vec)
                else:
                    geom_sway = (phi, vec)
                name = f"{combo.name} (imp {direction})"

            case = engine.run_case(model, loads, name=name, combo=combo.name,
                                   kind=combo.kind, order=order,
                                   imp_direction=direction,
                                   geom_sway=geom_sway)
            if order == 2 and case.converged and model.analysis.compute_alpha_cr:
                # first-order companion for the alpha_cr / sway-amplification
                # estimate (skipped when compute_alpha_cr is off, to save a solve)
                lin = engine.run_case(model, loads, name=name + " [1st]",
                                      combo=combo.name, kind=combo.kind,
                                      order=1, imp_direction=direction,
                                      geom_sway=geom_sway)
                if lin.converged:
                    case.sway_first_order = lin.max_sway
            results.append(case)

    if model.seismic and model.seismic.enabled:
        from .seismic import run_seismic
        results += run_seismic(model, progress=progress)

    # surface a stopped/diverged analysis on the command prompt: a combination
    # whose second-order solve did not converge means the structure is unstable
    # under that case and the analysis effectively stopped there.
    stopped = [c.name for c in results if not c.converged]
    if stopped:
        msg = ("ANALYSIS STOPPED - did not converge: "
               + ", ".join(stopped[:6]) + ("..." if len(stopped) > 6 else ""))
        print(msg, file=sys.stderr, flush=True)
        step(msg, 1.0)

    return results
