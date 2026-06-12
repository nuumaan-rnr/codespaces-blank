"""EN 15512 design checks on the analysis results.

Implemented verifications (clause references EN 15512 / EN 1993-1-1; all
partial factors and limits are configurable in CheckSettings):

  STRESS     cross-section resistance, linear interaction
             |N|/(A_eff*fy/gM0) + |M|/(W_eff*fy/gM0) <= 1
  BUCKLING   in-plane flexural buckling of compression members,
             |Nc|/(chi*A_eff*fy/gM1) + kM*|M|/(W_eff*fy/gM1) <= 1
             with chi from EN 1993-1-1 6.3.1 buckling curves and
             Ncr = pi^2*E*I/Lcr^2 (Lcr = K*L or explicit).
  CONNECTOR  hinge moment |M_end| <= M_Rd of the connector (from tests).
  DEFLECTION (SLS) beam transverse deflection <= L / limit_ratio.
  SWAY       (SLS) max horizontal displacement <= H / limit_ratio.
  ALPHA_CR   sway-sensitivity report: estimated elastic critical load
             factor from 1st/2nd-order sway amplification.  Informative
             when a second-order analysis was run (always satisfied by the
             analysis itself); flagged if alpha_cr is very low (< 3, near
             elastic instability).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from ..model import RackModel
from ..results import CaseResult
from . import buckling


@dataclass
class CheckResult:
    check: str                 # STRESS | BUCKLING | CONNECTOR | DEFLECTION | SWAY | ALPHA_CR
    case: str                  # analysis case name
    target: str                # 'member 3', 'node 12', 'frame'
    member_set: str
    utilization: float         # demand / capacity (<= 1 passes)
    detail: str = ""
    informative: bool = False  # reported but not part of the verdict

    @property
    def ok(self) -> bool:
        return self.informative or self.utilization <= 1.0 + 1e-9

    @property
    def status(self) -> str:
        if self.informative:
            return "INFO"
        return "PASS" if self.utilization <= 1.0 + 1e-9 else "FAIL"


def run_checks(model: RackModel, cases: List[CaseResult]) -> List[CheckResult]:
    out: List[CheckResult] = []
    for case in cases:
        if not case.converged:
            out.append(CheckResult(
                "STABILITY", case.name, "frame", "-", 99.0,
                "second-order analysis did not converge - the structure is "
                "likely unstable under this combination"))
            continue
        if case.kind == "ULS":
            out += _stress_checks(model, case)
            out += _buckling_checks(model, case)
            out += _connector_checks(model, case)
            a = _alpha_cr_check(model, case)
            if a:
                out.append(a)
        else:
            out += _deflection_checks(model, case)
            out.append(_sway_check(model, case))
    return out


# --------------------------------------------------------------------- ULS
def _stress_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    g = model.checks.gamma_M0
    for mid, mr in case.members.items():
        m = model.members[mid]
        sec = model.section_of(m)
        fy = model.material_of(m).fy
        N_rd = sec.area_eff * fy / g
        M_rd = sec.mod_eff * fy / g
        eta, st_worst = 0.0, None
        for s in mr.stations:
            e = abs(s.N) / N_rd + (abs(s.M) / M_rd if m.mtype == "beam" else 0.0)
            if e > eta:
                eta, st_worst = e, s
        detail = (f"N={st_worst.N/1e3:.1f} kN, M={st_worst.M/1e6:.2f} kNm "
                  f"at x={st_worst.x:.0f} mm; "
                  f"N_Rd={N_rd/1e3:.1f} kN, M_Rd={M_rd/1e6:.2f} kNm")
        res.append(CheckResult("STRESS", case.name, f"member {mid}",
                               m.member_set, eta, detail))
    return res


def _buckling_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    g = model.checks.gamma_M1
    kM = model.checks.k_M
    for mid, mr in case.members.items():
        m = model.members[mid]
        if mr.N_min >= 0.0:
            continue                      # no compression
        sec = model.section_of(m)
        mat = model.material_of(m)
        L_cr = m.L_buckling if m.L_buckling else m.k_buckling * mr.length
        N_cr = buckling.n_cr(mat.E, sec.I, L_cr)
        lam = buckling.lambda_bar(sec.area_eff, mat.fy, N_cr)
        chi = buckling.chi(lam, sec.buckling_curve)
        Nb_rd = chi * sec.area_eff * mat.fy / g
        M_rd = sec.mod_eff * mat.fy / g
        Nc = abs(mr.N_min)
        Mmax = mr.M_absmax if m.mtype == "beam" else 0.0
        eta = Nc / Nb_rd + kM * Mmax / M_rd
        detail = (f"Nc={Nc/1e3:.1f} kN, M={Mmax/1e6:.2f} kNm; "
                  f"Lcr={L_cr:.0f} mm, lambda={lam:.2f}, "
                  f"chi={chi:.3f} (curve {sec.buckling_curve}), "
                  f"Nb_Rd={Nb_rd/1e3:.1f} kN")
        res.append(CheckResult("BUCKLING", case.name, f"member {mid}",
                               m.member_set, eta, detail))
    return res


def _connector_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    for mid, mr in case.members.items():
        m = model.members[mid]
        for end, hinge in (("i", m.hinge_i), ("j", m.hinge_j)):
            if hinge is None or hinge.m_rd is None:
                continue
            M = abs(mr.M_end(end))
            res.append(CheckResult(
                "CONNECTOR", case.name, f"member {mid} end {end}",
                m.member_set, M / hinge.m_rd,
                f"M_Ed={M/1e6:.3f} kNm, M_Rd={hinge.m_rd/1e6:.3f} kNm"))
    return res


def _alpha_cr_check(model: RackModel, case: CaseResult) -> Optional[CheckResult]:
    a = case.alpha_cr_estimate
    if a is None:
        return None
    # second-order effects are already inside the analysis results, so this
    # is a stability *report*: utilization vs near-instability (alpha_cr = 3)
    eta = 3.0 / a
    note = ""
    if a < model.checks.alpha_cr_warn:
        note = (f" (alpha_cr < {model.checks.alpha_cr_warn:.0f}: sway frame, "
                "second-order analysis required - and performed)")
    return CheckResult(
        "ALPHA_CR", case.name, "frame", "-", eta,
        f"estimated alpha_cr={a:.2f}, sway amplification="
        f"{case.max_sway / case.sway_first_order:.3f}{note}",
        informative=True)


# --------------------------------------------------------------------- SLS
def _deflection_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    """Transverse deflection of (near-)horizontal beams vs span/limit."""
    res = []
    ratio = model.checks.beam_defl_limit_ratio
    for mid, mr in case.members.items():
        m = model.members[mid]
        if m.mtype != "beam":
            continue
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        if abs(nj.y - ni.y) > abs(nj.x - ni.x):
            continue                      # vertical-ish: treated by sway
        limit = mr.length / ratio
        d = mr.defl_absmax
        res.append(CheckResult(
            "DEFLECTION", case.name, f"member {mid}", m.member_set,
            d / limit,
            f"defl={d:.2f} mm, limit=L/{ratio:.0f}={limit:.2f} mm"))
    return res


def _sway_check(model: RackModel, case: CaseResult) -> CheckResult:
    H = model.height()
    limit = H / model.checks.sway_limit_ratio
    d = case.max_sway
    return CheckResult(
        "SWAY", case.name, "frame", "-", d / limit if limit > 0 else 0.0,
        f"max sway={d:.2f} mm, limit=H/{model.checks.sway_limit_ratio:.0f}"
        f"={limit:.2f} mm (H={H:.0f} mm)")


# ------------------------------------------------------------------ summary
def governing(checks: List[CheckResult]) -> Optional[CheckResult]:
    real = [c for c in checks if not c.informative]
    return max(real, key=lambda c: c.utilization) if real else None


def all_ok(checks: List[CheckResult]) -> bool:
    return all(c.ok for c in checks)
