"""Markdown report of the analysis and EN 15512 checks."""

from __future__ import annotations

from typing import List

from .checks.en15512 import CheckResult, all_ok, governing
from .model import RackModel
from .results import CaseResult

# member sets unique to the drive-in / drive-through / radio-shuttle builder
_DRIVEIN_SETS = ("rail beams", "rail arms", "spine bracing", "portal beams",
                 "back beams")


def is_drive_in(model: RackModel) -> bool:
    """True when the model was built by the multi-deep (drive-in / shuttle)
    builder, detected from its characteristic member sets."""
    sets = {m.member_set for m in model.members.values()}
    return bool({"rail beams", "rail arms"} & sets)


def drivein_summary(model: RackModel, checks: List[CheckResult]):
    """Drive-in / shuttle specific verification summary, or ``None`` for other
    systems.  Surfaces the quantities unique to a multi-deep drive-in rack:

      * the down-aisle (cantilever) upright effective length taken from the
        critical-upright buckling eigenvalue (FEM 10.2.07) - much shorter than
        the full frame height because the engine already resolves the
        second-order sway;
      * the cross-aisle braced effective length;
      * the pallet-support RAIL and cantilever ARM deflections (EN 15620);
      * the down-aisle vs cross-aisle frame sway;
      * the governing down-aisle upright flexural buckling.

    Returns a dict with ``Lcr_z``/``Lcr_y``/``H`` and a ``rows`` list of
    ``(label, utilization, status, detail)`` tuples (worst first), so every
    report format can render the same content.
    """
    if not is_drive_in(model):
        return None

    H = model.height()
    ups = [m for m in model.members.values() if m.member_set == "uprights"]
    lz = [m.L_buckling_z for m in ups if m.L_buckling_z]
    ly = [m.L_buckling_y for m in ups if m.L_buckling_y]
    Lcr_z = max(lz) if lz else None
    Lcr_y = max(ly) if ly else None

    def worst(check: str, member_set: str = None):
        rows = [c for c in checks if c.check == check
                and (member_set is None or c.member_set == member_set)]
        return max(rows, key=lambda c: c.utilization) if rows else None

    rows = []

    def add(label: str, c: CheckResult):
        if c is not None:
            rows.append((label, c.utilization, c.status, f"{c.detail} [{c.case}]"))

    add("Pallet-support rail deflection (EN 15620)",
        worst("DEFLECTION", "rail beams"))
    add("Cantilever arm deflection (EN 15620)",
        worst("DEFLECTION", "rail arms"))
    add("Down-aisle upright buckling (FEM 10.2.07)",
        worst("BUCKLING", "uprights"))
    # sway checks: targets read 'frame X (down-aisle)' / 'frame Y (cross-aisle)'
    sway = sorted((c for c in checks if c.check == "SWAY"),
                  key=lambda c: -c.utilization)
    da = next((c for c in sway if "down-aisle" in c.target), None)
    ca = next((c for c in sway if "cross-aisle" in c.target), None)
    add("Down-aisle frame sway", da)
    add("Cross-aisle frame sway", ca)

    return {"H": H, "Lcr_z": Lcr_z, "Lcr_y": Lcr_y, "rows": rows}


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

    lines += _drivein_section(model, checks)
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


def _drivein_section(model: RackModel,
                     checks: List[CheckResult]) -> List[str]:
    """Markdown 'Drive-in verification' section (empty for other systems)."""
    d = drivein_summary(model, checks)
    if d is None:
        return []
    out = ["## Drive-in verification (EN 15620 / FEM 10.2.07)", ""]
    H = d["H"]
    if d["Lcr_z"]:
        out.append(f"- Down-aisle upright effective length L_cr,z = "
                   f"{d['Lcr_z']:.0f} mm = {d['Lcr_z'] / H:.2f}*H "
                   f"(critical-upright buckling eigenvalue; the full "
                   f"second-order sway is already in the analysis, so the "
                   f"member check does **not** use the K=1.0 full height).")
    if d["Lcr_y"]:
        out.append(f"- Cross-aisle upright effective length L_cr,y = "
                   f"{d['Lcr_y']:.0f} mm (braced by the depth-frame ladders).")
    out.append(f"- Frame height H = {H:.0f} mm.")
    out += ["",
            "| verification | utilization | status | detail |",
            "|---|---|---|---|"]
    for label, util, status, detail in d["rows"]:
        out.append(f"| {label} | {util:.3f} | {status} | {detail} |")
    out.append("")
    out.append("*Pallet-support rail / cantilever-arm deflections include "
               "shear deformation (Timoshenko) and are limited to L/"
               f"{model.checks.beam_defl_limit_ratio:.0f} per EN 15620; the "
               "down-aisle uprights are vertical cantilevers braced cross-aisle "
               "only.*")
    out.append("")
    return out


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
