"""EN 15512 design checks on the analysis results (3D).

Implemented verifications (clause references EN 15512 / EN 1993-1-1; all
partial factors and limits are configurable in CheckSettings):

  STRESS     cross-section resistance, linear interaction at every station
             |N|/(A_eff*fy/gM0) + |My|/(Wy_eff*fy/gM0)
                                + |Mz|/(Wz_eff*fy/gM0) <= 1
  BUCKLING   flexural buckling of compression members about both local
             axes, chi from EN 1993-1-1 6.3.1 buckling curves,
             Ncr = pi^2*E*I/Lcr^2 per axis (Lcr = K*L or explicit):
             |Nc|/(chi_min*A_eff*fy/gM1) + kM*|My|/(Wy_eff*fy/gM1)
                                         + kM*|Mz|/(Wz_eff*fy/gM1) <= 1
  CONNECTOR  hinge end moments vs the connector resistances M_Rd,z / M_Rd,y
             from tests.
  DEFLECTION (SLS) beam transverse deflection (resultant relative to the
             chord) <= L / limit_ratio.
  SWAY       (SLS) max horizontal displacement in X and in Y <= H / ratio.
  ALPHA_CR   informative sway-sensitivity report from the 1st/2nd-order
             sway amplification (second-order effects are already inside
             the analysis results).
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
            out += _sway_checks(model, case)
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
        My_rd = sec.mod_y_eff * fy / g
        Mz_rd = sec.mod_z_eff * fy / g
        eta, st_worst = -1.0, None
        for s in mr.stations:
            e = abs(s.N) / N_rd
            if m.mtype == "beam":
                e += abs(s.My) / My_rd + abs(s.Mz) / Mz_rd
            if e > eta:
                eta, st_worst = e, s
        detail = (f"N={st_worst.N/1e3:.1f} kN, My={st_worst.My/1e6:.2f} kNm, "
                  f"Mz={st_worst.Mz/1e6:.2f} kNm at x={st_worst.x:.0f} mm; "
                  f"N_Rd={N_rd/1e3:.1f} kN, My_Rd={My_rd/1e6:.2f} kNm, "
                  f"Mz_Rd={Mz_rd/1e6:.2f} kNm")
        res.append(CheckResult("STRESS", case.name, f"member {mid}",
                               m.member_set, eta, detail))
    return res


def _buckling_targets(model: RackModel) -> Optional[set]:
    """Member sets to buckling-check; None = every compressed member."""
    if model.checks.buckling_sets is not None:
        return set(model.checks.buckling_sets)
    auto = {m.member_set for m in model.members.values()
            if m.member_set == "uprights"
            or model.section_of(m).role == "upright"}
    return auto or None


def _buckling_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    g = model.checks.gamma_M1
    kM = model.checks.k_M
    targets = _buckling_targets(model)
    for mid, mr in case.members.items():
        m = model.members[mid]
        if targets is not None and m.member_set not in targets:
            continue                      # EN 15512: buckling on uprights only
        if mr.N_min >= 0.0:
            continue                      # no compression
        sec = model.section_of(m)
        mat = model.material_of(m)
        Lcr_y = m.L_buckling_y if m.L_buckling_y else m.k_buckling_y * mr.length
        Lcr_z = m.L_buckling_z if m.L_buckling_z else m.k_buckling_z * mr.length
        Ncr_y = buckling.n_cr(mat.E, sec.Iy, Lcr_y)
        Ncr_z = buckling.n_cr(mat.E, sec.Iz, Lcr_z)
        lam_y = buckling.lambda_bar(sec.area_eff, mat.fy, Ncr_y)
        lam_z = buckling.lambda_bar(sec.area_eff, mat.fy, Ncr_z)
        chi_y = buckling.chi(lam_y, sec.buckling_curve_y)
        chi_z = buckling.chi(lam_z, sec.buckling_curve_z)
        chi_min = min(chi_y, chi_z)
        Nb_rd = chi_min * sec.area_eff * mat.fy / g
        My_rd = sec.mod_y_eff * mat.fy / g
        Mz_rd = sec.mod_z_eff * mat.fy / g
        Nc = abs(mr.N_min)
        eta = Nc / Nb_rd
        if m.mtype == "beam":
            eta += kM * mr.My_absmax / My_rd + kM * mr.Mz_absmax / Mz_rd
        gov = "y" if chi_y <= chi_z else "z"
        detail = (f"Nc={Nc/1e3:.1f} kN, My={mr.My_absmax/1e6:.2f} kNm, "
                  f"Mz={mr.Mz_absmax/1e6:.2f} kNm; "
                  f"Lcr_y={Lcr_y:.0f}, Lcr_z={Lcr_z:.0f} mm, "
                  f"lambda_y={lam_y:.2f}, lambda_z={lam_z:.2f}, "
                  f"chi={chi_min:.3f} (about {gov}, curve "
                  f"{sec.buckling_curve_y if gov == 'y' else sec.buckling_curve_z}), "
                  f"Nb_Rd={Nb_rd/1e3:.1f} kN")
        res.append(CheckResult("BUCKLING", case.name, f"member {mid}",
                               m.member_set, eta, detail))
    return res


def _connector_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    for mid, mr in case.members.items():
        m = model.members[mid]
        for end, hinge in (("i", m.hinge_i), ("j", m.hinge_j)):
            if hinge is None:
                continue
            st = mr.end(end)
            for axis, m_rd, M in (("z", hinge.m_rd_z, st.Mz),
                                  ("y", hinge.m_rd_y, st.My)):
                if m_rd is None:
                    continue
                res.append(CheckResult(
                    "CONNECTOR", case.name, f"member {mid} end {end} ({axis})",
                    m.member_set, abs(M) / m_rd,
                    f"M{axis},Ed={abs(M)/1e6:.3f} kNm, "
                    f"M{axis},Rd={m_rd/1e6:.3f} kNm"))
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
        note = (f" (alpha_cr < {model.checks.alpha_cr_warn:.0f}: sway-"
                "sensitive, second-order analysis required - and performed)")
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
        run = ((nj.x - ni.x) ** 2 + (nj.y - ni.y) ** 2) ** 0.5
        if abs(nj.z - ni.z) > run:
            continue                      # vertical-ish: treated by sway
        limit = mr.length / ratio
        d = mr.defl_absmax
        res.append(CheckResult(
            "DEFLECTION", case.name, f"member {mid}", m.member_set,
            d / limit,
            f"defl={d:.2f} mm, limit=L/{ratio:.0f}={limit:.2f} mm"))
    return res


def _sway_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    H = model.height()
    ratio = model.checks.sway_limit_ratio
    limit = H / ratio if H > 0 else 0.0
    out = []
    for axis, d in (("X (down-aisle)", case.max_sway_x),
                    ("Y (cross-aisle)", case.max_sway_y)):
        out.append(CheckResult(
            "SWAY", case.name, f"frame {axis}", "-",
            d / limit if limit > 0 else 0.0,
            f"max sway={d:.2f} mm, limit=H/{ratio:.0f}={limit:.2f} mm "
            f"(H={H:.0f} mm)"))
    return out


# ------------------------------------------------------------------ summary
def governing(checks: List[CheckResult]) -> Optional[CheckResult]:
    real = [c for c in checks if not c.informative]
    return max(real, key=lambda c: c.utilization) if real else None


def all_ok(checks: List[CheckResult]) -> bool:
    return all(c.ok for c in checks)
