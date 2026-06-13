"""Runs all combinations: assembles factored loads, applies the EN 15512
sway imperfection (EHF or initial geometry, in the configured horizontal
directions), solves first and second order, and returns the analysis
cases."""

from __future__ import annotations

from typing import List

from .combos import apply_ehf, assemble
from .engine.opensees import OpenSeesEngine
from .model import DIRECTION_VECTORS, RackModel
from .results import CaseResult


def run_all(model: RackModel) -> List[CaseResult]:
    errors = model.validate()
    if errors:
        raise ValueError("Model validation failed:\n  " + "\n  ".join(errors))

    engine = OpenSeesEngine()
    order = model.analysis.order
    results: List[CaseResult] = []

    for combo in model.combinations:
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
                phi = model.imperfection.value()
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
            if order == 2 and case.converged:
                # first-order companion for the alpha_cr / sway-amplification
                # estimate
                lin = engine.run_case(model, loads, name=name + " [1st]",
                                      combo=combo.name, kind=combo.kind,
                                      order=1, imp_direction=direction,
                                      geom_sway=geom_sway)
                if lin.converged:
                    case.sway_first_order = lin.max_sway
            results.append(case)

    return results
