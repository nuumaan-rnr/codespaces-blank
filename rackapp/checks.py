"""EN 15512 design checks on the analysis results.

Implemented (down-aisle spine model, internal forces from 2nd-order analysis):

  ULS (per ULS combination, gamma_M per config):
    * cross-section resistance      N/(A_eff*fy/gM0) + M/(W_eff*fy/gM0) <= 1
    * flexural buckling, uprights   N/(chi*A_eff*fy/gM1) + M/(W_eff*fy/gM1) <= 1
        chi per EN 1993-1-1 buckling curve (alpha configurable; rack uprights
        typically curve b/c, or chi derived from EN 15512 stub-column tests),
        buckling length = K * segment length between beam levels
    * beam-end connector            |M_connector| <= M_Rd (from tests)

  SLS:
    * pallet beam deflection        delta <= L / limit   (default L/200)
    * down-aisle sway               u_top <= H / limit   (default H/200)

Notes:
  - Because the global analysis is second order *with* sway imperfections,
    sway buckling is covered by the analysis; member checks then use the
    system length (K = 1.0 default), per the design-by-2nd-order route.
  - Distortional / torsional-flexural buckling of perforated uprights must be
    covered by the test-based effective properties supplied in the config
    (EN 15512 derives upright capacity from tests, not from calculation).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .config import RackConfig
from .model import RackModel, Member
from .results import AnalysisResults, ComboResult


@dataclass
class CheckResult:
    check: str          # "cross_section" | "buckling" | "connector" | "deflection" | "sway"
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
    if m.kind == "upright":
        return f"upright L{m.line} seg{m.level} (#{m.id})"
    return f"beam lvl{m.level} bay{m.bay} (#{m.id})"


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
    sls = [c for c in results.combos.values() if c.combo_id.startswith("SLS")]

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
            n_rd0 = sec.A * mat.fy / mat.gamma_M0
            m_rd0 = sec.Wy * mat.fy / mat.gamma_M0
            n_ed = r.N_max_compression
            m_ed = r.M_abs_max

            # cross-section interaction (linear, conservative)
            ratio = n_ed / n_rd0 + m_ed / m_rd0
            report.results.append(CheckResult(
                check="cross_section", combo=combo.combo_id,
                target=_member_label(m), demand=ratio, capacity=1.0,
                ratio=ratio, passed=ratio <= 1.0,
                note=f"N={n_ed/1e3:.1f} kN, M={m_ed/1e3:.2f} kNm",
            ))

            # flexural buckling of upright segments
            if m.kind == "upright" and n_ed > 0.0:
                L_cr = cc.K_upright * model.member_length(m.id)
                n_cr = math.pi**2 * mat.E * sec.Iy / L_cr**2
                lam = math.sqrt(sec.A * mat.fy / n_cr)
                chi = chi_buckling(lam, cc.buckling_alpha)
                n_b_rd = chi * sec.A * mat.fy / mat.gamma_M1
                m_rd1 = sec.Wy * mat.fy / mat.gamma_M1
                ratio_b = n_ed / n_b_rd + m_ed / m_rd1
                report.results.append(CheckResult(
                    check="buckling", combo=combo.combo_id,
                    target=_member_label(m), demand=ratio_b, capacity=1.0,
                    ratio=ratio_b, passed=ratio_b <= 1.0,
                    note=f"Lcr={L_cr:.2f} m, lambda={lam:.2f}, chi={chi:.2f}",
                ))

            # beam-end connector moment
            m_rd_conn = cfg.connections.beam_end_moment_resistance
            if m.kind == "beam" and m_rd_conn:
                m_conn = max(abs(r.M1), abs(r.M2))
                report.results.append(CheckResult(
                    check="connector", combo=combo.combo_id,
                    target=_member_label(m), demand=m_conn,
                    capacity=m_rd_conn, ratio=m_conn / m_rd_conn,
                    passed=m_conn <= m_rd_conn,
                    note=f"M_conn={m_conn/1e3:.2f} kNm vs M_Rd={m_rd_conn/1e3:.2f} kNm",
                ))

        # anchor uplift flag
        for nid, reac in combo.reactions.items():
            if reac.fz < -1.0:   # support pulls down on structure => uplift
                report.warnings.append(
                    f"{combo.combo_id}: uplift {abs(reac.fz)/1e3:.2f} kN at "
                    f"base node {nid} - anchor design required."
                )

    # ---------------- SLS checks --------------------------------------------
    for combo in sls:
        # pallet beam deflection
        for m in model.beams:
            r = combo.members.get(m.id)
            if r is None:
                continue
            L = model.member_length(m.id)
            limit = L / cc.beam_deflection_limit
            report.results.append(CheckResult(
                check="deflection", combo=combo.combo_id,
                target=_member_label(m), demand=r.defl_rel_max,
                capacity=limit, ratio=r.defl_rel_max / limit,
                passed=r.defl_rel_max <= limit,
                note=f"d={r.defl_rel_max*1e3:.1f} mm vs L/{cc.beam_deflection_limit:.0f}"
                     f"={limit*1e3:.1f} mm",
            ))

        # down-aisle sway at top
        u_top = max((abs(combo.nodes[n].ux) for n in model.top_nodes
                     if n in combo.nodes), default=0.0)
        limit = model.total_height / cc.sway_limit
        report.results.append(CheckResult(
            check="sway", combo=combo.combo_id, target="frame top",
            demand=u_top, capacity=limit,
            ratio=u_top / limit if limit > 0 else 0.0,
            passed=u_top <= limit,
            note=f"u={u_top*1e3:.1f} mm vs H/{cc.sway_limit:.0f}={limit*1e3:.1f} mm",
        ))

    return report
