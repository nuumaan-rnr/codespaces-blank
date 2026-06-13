"""Markdown report of the analysis and EN 15512 checks."""

from __future__ import annotations

from typing import List

from .checks.en15512 import CheckResult, all_ok, governing
from .model import RackModel
from .results import CaseResult


def write_report(model: RackModel, cases: List[CaseResult],
                 checks: List[CheckResult]) -> str:
    lines: List[str] = []
    add = lines.append

    add(f"# EN 15512 design check report - {model.name}")
    add("")
    add(f"- Analysis: {'second-order (P-Delta)' if model.analysis.order == 2 else 'first-order'} "
        f"elastic, engine: OpenSees")
    phi = None
    try:
        phi = model.imperfection.value()
    except ValueError:
        pass
    if phi is not None:
        add(f"- Sway imperfection: phi = {phi:.5f} rad "
            f"(1/{1/phi:.0f}), method = {model.imperfection.method}")
    add(f"- Partial factors: gamma_M0 = {model.checks.gamma_M0}, "
        f"gamma_M1 = {model.checks.gamma_M1}")
    add(f"- Members: {len(model.members)}, nodes: {len(model.nodes)}, "
        f"height: {model.height():.0f} mm")
    add("")

    add("## Load combinations")
    add("")
    add("| combination | kind | load factors | imperfection |")
    add("|---|---|---|---|")
    for c in model.combinations:
        factors = " + ".join(f"{f:g} x {lc}" for lc, f in c.factors.items())
        if c.imperfection and (c.kind == "ULS" or c.imp_directions):
            dirs = c.imp_directions or model.imperfection.directions
            imp = ", ".join(dirs)
        else:
            imp = "-"
        add(f"| {c.name} | {c.kind} | {factors} | {imp} |")
    add("")

    add("## Analysis cases")
    add("")
    add("| case | kind | converged | sway X [mm] | sway Y [mm] | alpha_cr (est.) |")
    add("|---|---|---|---|---|---|")
    for c in cases:
        a = c.alpha_cr_estimate
        add(f"| {c.name} | {c.kind} | {'yes' if c.converged else '**NO**'} "
            f"| {c.max_sway_x:.2f} | {c.max_sway_y:.2f} "
            f"| {f'{a:.2f}' if a else '-'} |")
    add("")

    gov = governing(checks)
    verdict = "PASS" if all_ok(checks) else "FAIL"
    add(f"## Verdict: **{verdict}**")
    if gov:
        add("")
        add(f"Governing: {gov.check} on {gov.target} ({gov.member_set}) in "
            f"'{gov.case}' - utilization **{gov.utilization:.3f}**")
    add("")

    lines += _level_wise_utilization(model, checks)

    for kind in ("STRESS", "BUCKLING", "BRACE_BUCKLING", "CONNECTOR",
                 "BRACE_BOLT", "BASEPLATE", "BASE_RESTRAINT", "ANCHORAGE",
                 "SPLICE", "DEFLECTION", "SWAY", "ALPHA_CR", "STABILITY"):
        rows = [c for c in checks if c.check == kind]
        if not rows:
            continue
        add(f"## {kind} checks")
        add("")
        add("| target | set | case | utilization | status | detail |")
        add("|---|---|---|---|---|---|")
        # worst first, cap very long tables at the 40 worst rows
        rows.sort(key=lambda c: -c.utilization)
        for c in rows[:40]:
            add(f"| {c.target} | {c.member_set} | {c.case} "
                f"| {c.utilization:.3f} | {c.status} | {c.detail} |")
        if len(rows) > 40:
            add(f"| ... | | | | | {len(rows) - 40} more rows omitted |")
        add("")

    add("---")
    add("*Defaults follow EN 15512 with EN 1993 buckling curves; verify all "
        "factors, imperfection parameters and section/connector test values "
        "against the edition of the standard applicable to your project.*")
    return "\n".join(lines)


def _level_wise_utilization(model: RackModel,
                            checks: List[CheckResult]) -> List[str]:
    """Worst utilization per beam level: the beams and connectors AT the
    level, and the uprights / bracing of the storey band BELOW it."""
    beam_z = sorted({model.nodes[m.node_i].z
                     for m in model.members.values()
                     if m.member_set == "pallet beams"})
    if not beam_z:
        return []
    bands = [0.0] + beam_z

    def band_of(z: float) -> int:
        for k in range(len(bands) - 1):
            if bands[k] - 1.0 <= z <= bands[k + 1] + 1.0:
                return k + 1
        return len(bands) - 1

    # member id -> (level index, group)
    where = {}
    for m in model.members.values():
        zi, zj = model.nodes[m.node_i].z, model.nodes[m.node_j].z
        if m.member_set == "pallet beams":
            where[m.id] = (band_of(zi), "beams")
        elif m.member_set == "uprights":
            where[m.id] = (band_of((zi + zj) / 2.0), "uprights")
        else:
            where[m.id] = (band_of((zi + zj) / 2.0), "bracing")

    worst = {}     # (level, group) -> CheckResult
    for c in checks:
        if c.informative or not c.target.startswith("member"):
            continue
        mid = int(c.target.split()[1])
        if mid not in where:
            continue
        level, group = where[mid]
        if c.check == "CONNECTOR":
            group = "connectors"
        key = (level, group)
        if key not in worst or c.utilization > worst[key].utilization:
            worst[key] = c

    out = ["## Utilization by level", "",
           "Beams and connectors at the level; uprights and bracing of the "
           "storey below it.", "",
           "| level | elevation [mm] | uprights | beams | connectors "
           "| bracing |", "|---|---|---|---|---|---|"]
    for k, z in enumerate(beam_z, start=1):
        cells = []
        for group in ("uprights", "beams", "connectors", "bracing"):
            c = worst.get((k, group))
            if c is None:
                cells.append("-")
            else:
                cells.append(f"{c.utilization:.3f} {c.status} ({c.check}, "
                             f"member {c.target.split()[1]})")
        out.append(f"| {k} | {z:.0f} | " + " | ".join(cells) + " |")
    out.append("")
    return out
