"""Report generation: markdown summary + JSON dump of results and checks."""

from __future__ import annotations

import json
from dataclasses import asdict

from .checks import CheckReport
from .config import RackConfig
from .model import RackModel
from .results import AnalysisResults

CHECK_TITLES = {
    "cross_section": "Cross-section resistance, biaxial (EN 15512 9.7.2)",
    "buckling": "Flexural buckling of uprights, biaxial (EN 15512 9.7 / EC3 6.3)",
    "brace": "Frame bracing axial buckling",
    "connector": "Beam-end connector moment (test-based M_Rd)",
    "deflection": "Pallet beam deflection (SLS)",
    "sway": "Sway at SLS (down-aisle / cross-aisle)",
}


def to_markdown(cfg: RackConfig, model: RackModel, results: AnalysisResults,
                report: CheckReport) -> str:
    geo = cfg.geometry
    lines = [
        f"# EN 15512 check report - {cfg.name}",
        "",
        f"- Engine: **{results.engine}** (3D model)",
        f"- Bays x levels: **{geo.n_bays} x {geo.n_levels}**, "
        f"bay width {geo.bay_width:.2f} m, frame depth {geo.depth:.2f} m, "
        f"total height {geo.total_height:.2f} m",
        f"- Frame bracing: {geo.bracing.pattern} "
        f"(panel {geo.bracing.panel_height:.2f} m)",
        f"- Upright: {cfg.upright_section.name}  |  Beam: {cfg.beam_section.name}"
        f"  |  Brace: {cfg.brace_section.name}",
        f"- Material: {cfg.material.name} (fy = {cfg.material.fy/1e6:.0f} MPa)",
        f"- Beam-end connector stiffness: "
        f"{cfg.connections.beam_end_stiffness/1e3:.1f} kNm/rad, "
        f"base stiffness: {cfg.connections.base_stiffness/1e3:.1f} kNm/rad "
        f"(down-aisle) / {cfg.connections.base_cross/1e3:.1f} kNm/rad (cross)",
        f"- Sway imperfections: phi_x = {cfg.sway_imperfection_x():.5f} rad, "
        f"phi_y = {cfg.sway_imperfection_y():.5f} rad "
        f"(applied as equivalent horizontal forces)",
        "",
        "## Analysis",
        "",
        "| Combination | Type | 2nd order | Converged | Iterations |",
        "|---|---|---|---|---|",
    ]
    for cid, cr in results.combos.items():
        lines.append(
            f"| {cid} | {'ULS' if cid.startswith('ULS') else 'SLS'} "
            f"| {'yes' if cr.second_order else 'no'} "
            f"| {'yes' if cr.converged else '**NO**'} | {cr.iterations} |"
        )

    verdict = "PASS" if report.all_passed else "FAIL"
    lines += ["", f"## Verdict: **{verdict}**", ""]

    for check, rs in report.by_check().items():
        gov = max(rs, key=lambda r: r.ratio)
        lines += [
            f"### {CHECK_TITLES.get(check, check)}",
            "",
            f"Governing: {gov.target} @ {gov.combo} - "
            f"utilization **{gov.ratio:.2f}** "
            f"({'OK' if gov.passed else 'EXCEEDED'}) - {gov.note}",
            "",
            "| Target | Combo | Utilization | Status | Detail |",
            "|---|---|---|---|---|",
        ]
        top = sorted(rs, key=lambda r: -r.ratio)[:10]
        for r in top:
            lines.append(
                f"| {r.target} | {r.combo} | {r.ratio:.2f} "
                f"| {'OK' if r.passed else '**FAIL**'} | {r.note} |"
            )
        if len(rs) > len(top):
            lines.append(f"| ... {len(rs) - len(top)} more | | | | |")
        lines.append("")

    if report.warnings or results.warnings:
        lines += ["## Warnings", ""]
        for w in results.warnings + report.warnings:
            lines.append(f"- {w}")
        lines.append("")

    lines += [
        "---",
        "*Stress, buckling, connector checks at ULS from the second-order 3D "
        "analysis with sway imperfections in both directions (biaxial My + Mz "
        "interaction); deflection and sway at SLS. Verify imperfection values, "
        "partial factors and test-based section/connection properties against "
        "the EN 15512 edition applicable to the project.*",
    ]
    return "\n".join(lines)


def to_json(cfg: RackConfig, model: RackModel, results: AnalysisResults,
            report: CheckReport) -> str:
    payload = {
        "name": cfg.name,
        "engine": results.engine,
        "sway_imperfection_x": cfg.sway_imperfection_x(),
        "sway_imperfection_y": cfg.sway_imperfection_y(),
        "combinations": {
            cid: {
                "second_order": cr.second_order,
                "converged": cr.converged,
                "iterations": cr.iterations,
                "nodes": {n: asdict(v) for n, v in cr.nodes.items()},
                "members": {m: asdict(v) for m, v in cr.members.items()},
                "reactions": {n: asdict(v) for n, v in cr.reactions.items()},
            }
            for cid, cr in results.combos.items()
        },
        "checks": [asdict(r) for r in report.results],
        "warnings": results.warnings + report.warnings,
        "all_passed": report.all_passed,
    }
    return json.dumps(payload, indent=2)
