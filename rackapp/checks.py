"""EN 15512 design checks on the analysis results (3D model, biaxial).

Implemented (internal forces from the second-order 3D analysis):

  ULS (per ULS combination, gamma_M per config):
    * cross-section resistance (biaxial, linear interaction)
        N/(A_eff*fy/gM0) + My/(Wy_eff*fy/gM0) + Mz/(Wz_eff*fy/gM0) <= 1
    * flexural buckling of uprights (biaxial)
        N/(chi_min*A_eff*fy/gM1) + My/(Wy_eff*fy/gM1) + Mz/(Wz_eff*fy/gM1) <= 1
        chi computed about BOTH axes (EN 1993-1-1 curves, alpha per axis,
        or per upright test data); chi_min governs. Buckling lengths:
        K_y/K_z x segment length (segments end at beam and brace nodes).
    * brace axial buckling      N <= chi*A*fy/gM1  (pin-ended, L_cr = L)
    * beam-end connector        |My_connector| <= M_Rd (from tests)

  SLS:
    * pallet beam deflection    delta <= L / limit   (default L/200)
    * sway, down-aisle (X)      u_top <= H / limit   on the SLS sway combo
    * sway, cross-aisle (Y)     u_top <= H / limit   on the SLS sway combo

Notes:
  - Because the global analysis is second order *with* sway imperfections in
    each direction, sway buckling is covered by the analysis; member checks
    then use the system (segment) length, per the design-by-2nd-order route.
  - Distortional / torsional-flexural buckling of perforated uprights must be
    covered by the test-based effective properties supplied in the config
    (EN 15512 derives upright capacity from tests, not from calculation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import RackConfig
from .model import RackModel, Member
from .results import AnalysisResults


@dataclass
class CheckResult:
    check: str          # cross_section | buckling | brace | connector | deflection | sway
    combo: str
    target: str         # human-readable member/node label
    demand: float
    capacity: float
    ratio: float
    passed: bool
    note: str = ""


@dataclass
class CheckReport:
    results: list[CheckResult] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def all_passed(self) -> bool:
        return all(r.passed for r in self.results)

    def governing(self, check: str | None = None) -> CheckResult | None:
        rs = [r for r in self.results if check is None or r.check == check]
        return max(rs, key=lambda r: r.ratio) if rs else None

    def by_check(self) -> dict[str, list[CheckResult]]:
        out: dict[str, list[CheckResult]] = {}
        for r in self.results:
            out.setdefault(r.check, []).append(r)
        return out


def _member_label(m: Member) -> str:
    face = {0: "F", 1: "R"}.get(m.face, "")
    if m.kind == "upright":
        return f"upright L{m.line}{face} seg{m.level} (#{m.id})"
    if m.kind == "brace":
        return f"brace L{m.line} panel{m.level} (#{m.id})"
    return f"beam lvl{m.level} bay{m.bay}{face} (#{m.id})"


def chi_buckling(lam_bar: float, alpha: float) -> float:
    """EN 1993-1-1 6.3.1.2 reduction factor."""
    if lam_bar <= 0.2:
        return 1.0
    phi = 0.5 * (1.0 + alpha * (lam_bar - 0.2) + lam_bar**2)
    return min(1.0, 1.0 / (phi + math.sqrt(max(phi**2 - lam_bar**2, 0.0))))


def run_checks(cfg: RackConfig, model: RackModel,
               results: AnalysisResults) -> CheckReport:
    report = CheckReport()
    mat = cfg.material
    cc = cfg.checks

    uls = [c for c in results.combos.values() if c.combo_id.startswith("ULS")]

    for combo in results.combos.values():
        if combo.second_order and not combo.converged:
            report.warnings.append(
                f"combination {combo.combo_id}: 2nd-order analysis did NOT "
                f"converge - structure may be unstable; checks unreliable."
            )

    # ---------------- ULS checks --------------------------------------------
    for combo in uls:
        for m in model.members.values():
            r = combo.members.get(m.id)
            if r is None:
                continue
            sec = m.section
            n_ed = r.N_max_compression
            my_ed = r.My_abs_max
            mz_ed = r.Mz_abs_max

            if m.kind == "brace":
                # pin-ended truss member: axial cross-section + buckling
                L_cr = model.member_length(m.id)
                n_cr = math.pi**2 * mat.E * min(sec.Iy, sec.Iz) / L_cr**2
                lam = math.sqrt(sec.A * mat.fy / n_cr)
                chi = chi_buckling(lam, cc.buckling_alpha_z)
                n_b_rd = chi * sec.A * mat.fy / mat.gamma_M1
                ratio = n_ed / n_b_rd if n_b_rd > 0 else 0.0
                report.results.append(CheckResult(
                    check="brace", combo=combo.combo_id,
                    target=_member_label(m), demand=n_ed, capacity=n_b_rd,
                    ratio=ratio, passed=ratio <= 1.0,
                    note=f"N={n_ed/1e3:.1f} kN, lambda={lam:.2f}, chi={chi:.2f}",
                ))
                continue

            # biaxial cross-section interaction (linear, conservative)
            n_rd0 = sec.A * mat.fy / mat.gamma_M0
            my_rd0 = sec.Wy * mat.fy / mat.gamma_M0
            mz_rd0 = sec.Wz * mat.fy / mat.gamma_M0
            ratio = n_ed / n_rd0 + my_ed / my_rd0 + mz_ed / mz_rd0
            report.results.append(CheckResult(
                check="cross_section", combo=combo.combo_id,
                target=_member_label(m), demand=ratio, capacity=1.0,
                ratio=ratio, passed=ratio <= 1.0,
                note=f"N={n_ed/1e3:.1f} kN, My={my_ed/1e3:.2f} kNm, "
                     f"Mz={mz_ed/1e3:.2f} kNm",
            ))

            # biaxial flexural buckling of upright segments
            if m.kind == "upright" and n_ed > 0.0:
                L = model.member_length(m.id)
                chis = {}
                for axis, I, K, alpha in (
                    ("y", sec.Iy, cc.K_upright_y, cc.buckling_alpha_y),
                    ("z", sec.Iz, cc.K_upright_z, cc.buckling_alpha_z),
                ):
                    n_cr = math.pi**2 * mat.E * I / (K * L) ** 2
                    lam = math.sqrt(sec.A * mat.fy / n_cr)
                    chis[axis] = (chi_buckling(lam, alpha), lam)
                chi_min = min(chis["y"][0], chis["z"][0])
                gov_axis = "y" if chis["y"][0] <= chis["z"][0] else "z"
                n_b_rd = chi_min * sec.A * mat.fy / mat.gamma_M1
                my_rd1 = sec.Wy * mat.fy / mat.gamma_M1
                mz_rd1 = sec.Wz * mat.fy / mat.gamma_M1
                ratio_b = n_ed / n_b_rd + my_ed / my_rd1 + mz_ed / mz_rd1
                report.results.append(CheckResult(
                    check="buckling", combo=combo.combo_id,
                    target=_member_label(m), demand=ratio_b, capacity=1.0,
                    ratio=ratio_b, passed=ratio_b <= 1.0,
                    note=f"chi_y={chis['y'][0]:.2f}, chi_z={chis['z'][0]:.2f} "
                         f"(axis {gov_axis} governs), N={n_ed/1e3:.1f} kN, "
                         f"My={my_ed/1e3:.2f}, Mz={mz_ed/1e3:.2f} kNm",
                ))

            # beam-end connector moment (about local y)
            m_rd_conn = cfg.connections.beam_end_moment_resistance
            if m.kind == "beam" and m_rd_conn:
                m_conn = max(abs(r.My1), abs(r.My2))
                report.results.append(CheckResult(
                    check="connector", combo=combo.combo_id,
                    target=_member_label(m), demand=m_conn,
                    capacity=m_rd_conn, ratio=m_conn / m_rd_conn,
                    passed=m_conn <= m_rd_conn,
                    note=f"M_conn={m_conn/1e3:.2f} kNm vs "
                         f"M_Rd={m_rd_conn/1e3:.2f} kNm",
                ))

        # anchor uplift flag
        for nid, reac in combo.reactions.items():
            if reac.fz < -1.0:   # support pulls down on structure => uplift
                report.warnings.append(
                    f"{combo.combo_id}: uplift {abs(reac.fz)/1e3:.2f} kN at "
                    f"base node {nid} - anchor design required."
                )

    # ---------------- SLS checks --------------------------------------------
    sls_defl = results.combos.get("SLS")
    if sls_defl:
        for m in model.beams:
            r = sls_defl.members.get(m.id)
            if r is None:
                continue
            L = model.member_length(m.id)
            limit = L / cc.beam_deflection_limit
            report.results.append(CheckResult(
                check="deflection", combo=sls_defl.combo_id,
                target=_member_label(m), demand=r.defl_rel_max,
                capacity=limit, ratio=r.defl_rel_max / limit,
                passed=r.defl_rel_max <= limit,
                note=f"d={r.defl_rel_max*1e3:.1f} mm vs "
                     f"L/{cc.beam_deflection_limit:.0f}={limit*1e3:.1f} mm",
            ))

    for combo_id, direction, attr in (("SLS_SWX", "down-aisle X", "ux"),
                                      ("SLS_SWY", "cross-aisle Y", "uy")):
        combo = results.combos.get(combo_id)
        if combo is None:
            continue
        u_top = max((abs(getattr(combo.nodes[n], attr))
                     for n in model.top_nodes if n in combo.nodes), default=0.0)
        limit = model.total_height / cc.sway_limit
        report.results.append(CheckResult(
            check="sway", combo=combo_id, target=f"frame top, {direction}",
            demand=u_top, capacity=limit,
            ratio=u_top / limit if limit > 0 else 0.0,
            passed=u_top <= limit,
            note=f"u={u_top*1e3:.1f} mm vs H/{cc.sway_limit:.0f}"
                 f"={limit*1e3:.1f} mm",
        ))

    return report
