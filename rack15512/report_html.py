"""Design Validation Report (self-contained HTML).

Produces an engineering report for an EN 15512 selective pallet racking
design: model summary, supports / stiffness, load cases and combinations,
2D (front / side / plan) and 3D model views with dimensions, and the full
set of design checks with their EN 15512 / EN 1993 clause references and a
pass / fail statement per member group.

The HTML embeds the figures as base64 PNGs so the file is fully portable
(open in any browser, print to PDF).
"""

from __future__ import annotations

import base64
import datetime as _dt
import html
import io
from typing import Dict, List, Optional

import matplotlib.pyplot as plt

from .checks.en15512 import CheckResult, all_ok, governing
from .model import RackModel
from .results import CaseResult
from .viewer import (plot_front_elevation, plot_model, plot_plan,
                     plot_side_elevation, plot_utilization)

# EN clause + verification basis per check type
CLAUSES = {
    "STRESS": ("EN 15512 §9.7.6 / §9.2",
               "Cross-section resistance under axial force and biaxial "
               "bending: |N|/(A_eff·f_y/γ_M) + |M_y|/(W_eff,y·f_y/γ_M) + "
               "|M_z|/(W_eff,z·f_y/γ_M) ≤ 1, effective section properties "
               "from tests / EN 1993-1-3."),
    "BUCKLING": ("EN 15512 §9.7.4, §9.7.5 / EN 1993-1-1 §6.3.1",
                 "Flexural and flexural-torsional buckling of the uprights: "
                 "N/N_b,Rd,min + M_y/M_Rd,y + M_z/M_Rd,z ≤ 1, with "
                 "N_b,Rd,min = χ_min·A_eff·f_y/γ_M, χ_min = min(χ_y, χ_z, "
                 "χ_FT). Buckling lengths: major = beam gap, minor = bracing "
                 "node spacing."),
    "BRACE_BUCKLING": ("EN 15512 §10.4 / §9.7.4-9.7.5",
                       "Compression buckling of the frame bracing members "
                       "(flexural + flexural-torsional, buckling curve c)."),
    "CONNECTOR": ("EN 15512 §9.5.4",
                  "Beam-end connector combined bending and shear: "
                  "M_Sd/M_Rd + (V_Sd − M_Rd/a)/V_Rd ≤ 1, M_Rd from Annex A "
                  "tests."),
    "BRACE_BOLT": ("EN 1993-1-8 Table 3.4",
                   "Bolted bracing connection: brace axial force ≤ n·min("
                   "bolt shear, bearing on brace, bearing on upright), "
                   "bearing F_b,Rd = k_1·α_b·f_u·d·t/γ_M2."),
    "BASEPLATE": ("EN 15512 §9.9.1, §9.10.1",
                  "Contact pressure on the floor: f_j = 2.5·f_ck/γ_c; the "
                  "upright load spreads over a strip of half-width "
                  "e = t·√(f_y/(3·f_j)); N_Sd ≤ f_j·A_bas."),
    "BASE_RESTRAINT": ("EN 15512 §10.5.1 / §8.4.2",
                       "Partial restraint of the upright base: "
                       "M_Sd,y / M_Rd(N_Sd) ≤ 1, M_Rd(N) from the "
                       "floor-connection tests."),
    "ANCHORAGE": ("EN 15512 §7.6, §9.10.4",
                  "Anchorage / overturning: base uplift ≤ anchor tension; "
                  "min 3 kN tension + 5 kN shear per connection."),
    "SPLICE": ("EN 1993-1-8 §3 (bolt group)",
               "Upright splice connection: elastic bolt-group check for the "
               "concurrent N, V and M; per-bolt min(shear, bearing)."),
    "DEFLECTION": ("EN 15512 §9.4.5",
                   "Beam deflection at SLS ≤ span/200 (or the configured "
                   "limit)."),
    "SWAY": ("EN 15512 §7.x (serviceability)",
             "Overall sway at SLS ≤ H/200 in both directions."),
    "ALPHA_CR": ("EN 15512 §9.7.2",
                 "Sway sensitivity (informative): second-order effects are "
                 "included in the analysis."),
    "STABILITY": ("EN 15512 §9.7.2",
                  "Second-order equilibrium / elastic stability."),
}


def _fig_b64(fig) -> str:
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight")
    plt.close(fig)
    return base64.b64encode(buf.getvalue()).decode("ascii")


def _img(fig, caption: str) -> str:
    return (f'<figure><img src="data:image/png;base64,{_fig_b64(fig)}"/>'
            f'<figcaption>{html.escape(caption)}</figcaption></figure>')


def _esc(x) -> str:
    return html.escape(str(x))


def design_validation_report(model: RackModel, cases: List[CaseResult],
                             checks: List[CheckResult],
                             meta: Optional[Dict] = None) -> str:
    """Return the full Design Validation Report as a standalone HTML string."""
    from . import branding as B
    meta = meta or {}
    verdict = all_ok(checks)
    gov = governing(checks)
    out: List[str] = []
    a = out.append

    a(_HEAD)
    a('<div class="page">')
    # branded header band with logo
    logo = B.logo_data_uri()
    a('<div class="brandbar">')
    if logo:
        a(f'<img class="logo" src="{logo}"/>')
    a(f'<div class="brandtxt"><div class="company">{_esc(B.COMPANY)}</div>'
      f'<div class="tag">{_esc(B.TAGLINE)} &middot; {_esc(B.WEBSITE)}</div>'
      f'</div></div>')
    a(f"<h1>Design Validation Report</h1>")
    a(f'<p class="sub">Selective pallet racking — EN 15512 '
      f'(second-order elastic, semi-rigid connections)</p>')
    a('<table class="meta">')
    for k in ("project", "system", "configuration", "client", "location",
              "engineer"):
        if meta.get(k):
            a(f"<tr><th>{k.title()}</th><td>{_esc(meta[k])}</td></tr>")
    a(f"<tr><th>Standard</th><td>EN 15512 (non-seismic); EN 1993-1-1, "
      f"-1-3, -1-8</td></tr>")
    a(f"<tr><th>Engine</th><td>OpenSees — 3D geometrically nonlinear "
      f"(P-Δ) elastic analysis</td></tr>")
    a(f"<tr><th>Date</th><td>{_dt.datetime.now():%Y-%m-%d %H:%M}</td></tr>")
    a("</table>")

    cls = "pass" if verdict else "fail"
    a(f'<div class="verdict {cls}">OVERALL RESULT: '
      f'{"PASS" if verdict else "FAIL"}</div>')
    if gov:
        a(f'<p>Governing check: <b>{_esc(gov.check)}</b> on '
          f'{_esc(gov.target)} ({_esc(gov.member_set)}) in '
          f'<i>{_esc(gov.case)}</i> — utilisation '
          f'<b>{gov.utilization:.3f}</b>.</p>')

    # ---- 1 model summary -------------------------------------------------
    a("<h2>1. Model summary</h2>")
    a("<table class='kv'>")
    a(f"<tr><th>Nodes / members</th><td>{len(model.nodes)} / "
      f"{len(model.members)}</td></tr>")
    a(f"<tr><th>Overall size (L×D×H)</th><td>{_extent(model)}</td></tr>")
    sets = {}
    for m in model.members.values():
        sets[m.member_set] = sets.get(m.member_set, 0) + 1
    a(f"<tr><th>Member groups</th><td>"
      + ", ".join(f"{k}: {v}" for k, v in sorted(sets.items()))
      + "</td></tr></table>")

    a("<h3>1.1 Sections</h3>")
    a("<table><thead><tr><th>Section</th><th>Role</th><th>f_y "
      "[MPa]</th><th>A [mm²]</th><th>A_eff</th><th>I_y [mm⁴]</th>"
      "<th>I_z [mm⁴]</th><th>J [mm⁴]</th></tr></thead><tbody>")
    for s in model.sections.values():
        fy = model.materials[s.material].fy
        a(f"<tr><td>{_esc(s.name)}</td><td>{_esc(s.role)}</td>"
          f"<td>{fy:.0f}</td><td>{s.A:.0f}</td><td>{s.area_eff:.0f}</td>"
          f"<td>{s.Iy:.3e}</td><td>{s.Iz:.3e}</td><td>{s.J:.3e}</td></tr>")
    a("</tbody></table>")

    # ---- 2 supports & stiffness -----------------------------------------
    a("<h2>2. Supports and stiffness modelling</h2>")
    a("<p>The base (floor-connection) rotational stiffness and the "
      "beam-to-upright connector stiffness are explicitly included in the "
      "analysis model, as required by EN 15512 §8.4.</p>")
    a(_support_table(model))
    a(_connector_table(model))

    # ---- 3 loads ---------------------------------------------------------
    a("<h2>3. Load cases and combinations</h2>")
    a("<table><thead><tr><th>Load case</th><th>Type</th></tr></thead><tbody>")
    for lc in model.load_cases.values():
        a(f"<tr><td>{_esc(lc.name)}</td><td>{_esc(lc.case_type)}</td></tr>")
    a("</tbody></table>")
    a("<table><thead><tr><th>Combination</th><th>Kind</th>"
      "<th>Load factors</th><th>Imperfection</th></tr></thead><tbody>")
    for c in model.combinations:
        fac = " + ".join(f"{f:g}·{lc}" for lc, f in c.factors.items())
        imp = (", ".join(c.imp_directions or model.imperfection.directions)
               if c.imperfection else "—")
        a(f"<tr><td>{_esc(c.name)}</td><td>{_esc(c.kind)}</td>"
          f"<td>{_esc(fac)}</td><td>{_esc(imp)}</td></tr>")
    a("</tbody></table>")
    try:
        phi = model.imperfection.value()
        a(f"<p>Global sway imperfection φ = {phi:.5f} rad (1/{1/phi:.0f}), "
          f"method {model.imperfection.method}, applied in "
          f"{', '.join(model.imperfection.directions)}.</p>")
    except ValueError:
        pass

    # ---- 4 model views ---------------------------------------------------
    a("<h2>4. Model views (dimensions in mm)</h2>")
    a('<div class="grid2">')
    a(_img(plot_front_elevation(model), "Front elevation (down-aisle, X-Z)"))
    a(_img(plot_side_elevation(model), "Side elevation (cross-aisle, Y-Z)"))
    a(_img(plot_plan(model), "Plan (top, X-Y)"))
    a(_img(plot_model(model), "3D view"))
    a("</div>")

    # ---- 5 analysis cases ------------------------------------------------
    a("<h2>5. Analysis cases — convergence</h2>")
    a("<table><thead><tr><th>Case</th><th>Kind</th><th>Converged</th>"
      "<th>Sway X [mm]</th><th>Sway Y [mm]</th><th>α_cr (est.)</th>"
      "</tr></thead><tbody>")
    for c in cases:
        acr = c.alpha_cr_estimate
        a(f"<tr><td>{_esc(c.name)}</td><td>{_esc(c.kind)}</td>"
          f"<td>{'yes' if c.converged else '<b>NO</b>'}</td>"
          f"<td>{c.max_sway_x:.2f}</td><td>{c.max_sway_y:.2f}</td>"
          f"<td>{f'{acr:.1f}' if acr else '—'}</td></tr>")
    a("</tbody></table>")

    # ---- 6 design checks -------------------------------------------------
    a("<h2>6. EN 15512 design verifications</h2>")
    a(_img(plot_utilization(model, checks),
          "Governing member utilisation (red > 1 fails)"))
    order = ["STRESS", "BUCKLING", "BRACE_BUCKLING", "CONNECTOR",
             "BRACE_BOLT", "BASEPLATE", "BASE_RESTRAINT", "ANCHORAGE",
             "SPLICE", "DEFLECTION", "SWAY", "ALPHA_CR", "STABILITY"]
    n = 1
    for kind in order:
        rows = [c for c in checks if c.check == kind]
        if not rows:
            continue
        clause, basis = CLAUSES.get(kind, ("", ""))
        rows.sort(key=lambda c: -c.utilization)
        worst = rows[0]
        grp_ok = all(c.ok for c in rows)
        a(f"<h3>6.{n} {kind} &mdash; {_esc(clause)}</h3>")
        n += 1
        a(f"<p class='basis'>{_esc(basis)}</p>")
        cls = "pass" if grp_ok else "fail"
        a(f"<p class='groupres {cls}'>{'PASS' if grp_ok else 'FAIL'} — "
          f"worst utilisation {worst.utilization:.3f} on "
          f"{_esc(worst.target)} ({_esc(worst.case)})"
          f"{' [informative]' if worst.informative else ''}.</p>")
        a("<table><thead><tr><th>Target</th><th>Set</th><th>Case</th>"
          "<th>Utilisation</th><th>Status</th><th>Detail</th></tr>"
          "</thead><tbody>")
        for c in rows[:30]:
            scls = "okrow" if c.ok else "failrow"
            a(f"<tr class='{scls}'><td>{_esc(c.target)}</td>"
              f"<td>{_esc(c.member_set)}</td><td>{_esc(c.case)}</td>"
              f"<td>{c.utilization:.3f}</td><td>{_esc(c.status)}</td>"
              f"<td>{_esc(c.detail)}</td></tr>")
        if len(rows) > 30:
            a(f"<tr><td colspan='6'>… {len(rows)-30} further rows "
              f"(see CSV / full report)</td></tr>")
        a("</tbody></table>")

    a(f"<hr/><p class='foot'>Generated by {_esc(B.COMPANY)} "
      f"{_esc(B.PRODUCT)} ({_esc(B.WEBSITE)}). This report is an "
      "engineering aid. All partial factors, imperfection parameters and "
      "section / connector / floor-connection test values must be verified "
      "by a qualified engineer against the applicable edition of EN 15512 "
      "and the national annex. Scope: non-seismic.</p>")
    a("</div></body></html>")
    return "\n".join(out)


def _extent(model) -> str:
    xs = [n.x for n in model.nodes.values()]
    ys = [n.y for n in model.nodes.values()]
    zs = [n.z for n in model.nodes.values()]
    return (f"{max(xs)-min(xs):.0f} × {max(ys)-min(ys):.0f} × "
            f"{max(zs)-min(zs):.0f} mm")


def _support_table(model) -> str:
    rows = ["<h3>2.1 Base / floor connections</h3>",
            "<table><thead><tr><th>Node</th><th>uX,uY,uZ</th>"
            "<th>k_rx [kNm/rad]</th><th>k_ry [kNm/rad]</th>"
            "<th>rz</th></tr></thead><tbody>"]
    def fmt(v):
        if v is True:
            return "fixed"
        if v is False:
            return "free"
        return f"{float(v)/1e6:.1f}"
    for s in model.supports:
        rows.append(
            f"<tr><td>{s.node}</td>"
            f"<td>{fmt(s.ux)},{fmt(s.uy)},{fmt(s.uz)}</td>"
            f"<td>{fmt(s.rx)}</td><td>{fmt(s.ry)}</td>"
            f"<td>{fmt(s.rz)}</td></tr>")
    rows.append("</tbody></table>")
    if model.base_plate and model.base_plate.m_rd_n:
        rows.append("<p>Base moment resistance M_Rd(N) from the "
                    "floor-connection test table is included for the "
                    "partial-restraint check (EN 15512 §10.5.1).</p>")
    return "\n".join(rows)


def _connector_table(model) -> str:
    seen = {}
    for m in model.members.values():
        if m.member_set == "pallet beams" and m.hinge_i:
            z = round(model.nodes[m.node_i].z)
            seen.setdefault((z, m.section), m.hinge_i)
    rows = ["<h3>2.2 Beam-to-upright connectors (per beam level)</h3>",
            "<table><thead><tr><th>Level z [mm]</th><th>Beam</th>"
            "<th>k_φ [kNm/rad]</th><th>M_Rd [kNm]</th>"
            "<th>looseness [mrad]</th></tr></thead><tbody>"]
    for (z, sec), h in sorted(seen.items()):
        rows.append(
            f"<tr><td>{z}</td><td>{_esc(sec)}</td>"
            f"<td>{(h.rz or 0)/1e6:.1f}</td>"
            f"<td>{(h.m_rd_z or 0)/1e6:.2f}</td>"
            f"<td>{(h.looseness or 0)*1e3:.1f}</td></tr>")
    rows.append("</tbody></table>")
    rows.append("<p>The connector rotational stiffness k_φ (semi-rigid "
                "beam end connection) and the beam flexural stiffness EI of "
                "the selected section are both included in the global "
                "analysis.</p>")
    return "\n".join(rows)


_HEAD = """<!doctype html><html><head><meta charset="utf-8">
<title>Design Validation Report</title>
<style>
 body{font-family:'Segoe UI',Arial,sans-serif;color:#333;margin:0;
   background:#f4f4f4}
 .page{max-width:1000px;margin:0 auto;background:#fff;padding:28px 40px}
 .brandbar{display:flex;align-items:center;gap:18px;
   border-bottom:3px solid #0C8490;padding-bottom:12px;margin-bottom:14px}
 .brandbar .logo{height:60px}
 .brandbar .company{font-size:18px;font-weight:bold;color:#545454}
 .brandbar .tag{font-size:12px;color:#0C8490}
 h1{margin:0 0 4px;font-size:25px;color:#545454}
 .sub{color:#666;margin:0 0 16px}
 h2{border-bottom:2px solid #0C8490;padding-bottom:4px;margin-top:28px;
   font-size:19px;color:#0C8490}
 h3{margin-top:20px;font-size:15px;color:#545454}
 table{border-collapse:collapse;width:100%;margin:8px 0;font-size:12px}
 th,td{border:1px solid #ccc;padding:4px 6px;text-align:left;
   vertical-align:top}
 thead th{background:#EAF3F4;color:#0C5660}
 table.meta,table.kv{width:auto}
 table.meta th,table.kv th{background:#EAF3F4;width:160px}
 .verdict{font-size:20px;font-weight:bold;padding:10px 14px;margin:14px 0;
   border-radius:6px;text-align:center;color:#fff}
 .verdict.pass{background:#0C8490}.verdict.fail{background:#c62828}
 .groupres{font-weight:bold;padding:6px 10px;border-radius:4px}
 .groupres.pass{background:#EAF3F4;color:#0C7080}
 .groupres.fail{background:#fdecea;color:#c62828}
 .basis{color:#555;font-size:12px;font-style:italic}
 tr.failrow td{background:#fdecea}
 figure{margin:8px 0;text-align:center}
 figure img{max-width:100%;border:1px solid #ddd}
 figcaption{font-size:12px;color:#555;margin-top:2px}
 .grid2{display:grid;grid-template-columns:1fr 1fr;gap:10px}
 .foot{font-size:11px;color:#777;margin-top:20px}
 hr{border:none;border-top:1px solid #ddd}
 @media print{body{background:#fff}.page{max-width:none}}
</style></head><body>"""
