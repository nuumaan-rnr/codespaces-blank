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

    for kind in ("STRESS", "BUCKLING", "CONNECTOR", "DEFLECTION", "SWAY",
                 "ALPHA_CR", "STABILITY"):
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
