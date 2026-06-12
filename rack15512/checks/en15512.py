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
  BRACE_BOLT bracing end connection (EN 1993-1-8): brace axial force vs
             n_bolts x min( bolt shear Fv,Rd,
                            bearing on the brace ply,
                            bearing on the upright ply ),
             bearing Fb,Rd = k1 * alpha_b * fu * d * t / gamma_M2 with
             alpha_b = min(e1/(3*d0), fub/fu, 1) and
             k1 = min(2.8*e2/d0 - 1.7, 2.5), using e1/e2/t/fu of each ply
             from the section master.  Enabled by CheckSettings.bolt_d.
  BASEPLATE  footplate per EN 1993-1-8 6.2.5: floor bearing
             N_Ed <= b*d*f_jd and cantilever-projection plate thickness
             t >= c * sqrt(3*f_jd*gamma_M0/fy); the minimum required plate
             size/thickness for the governing base reaction is reported.
             Enabled by RackModel.base_plate.
  DEFLECTION (SLS) beam transverse deflection (resultant relative to the
             chord) <= L / limit_ratio.
  SWAY       (SLS) max horizontal displacement in X and in Y <= H / ratio.
  ALPHA_CR   informative sway-sensitivity report from the 1st/2nd-order
             sway amplification (second-order effects are already inside
             the analysis results).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from ..model import CrossSection, RackModel
from ..results import CaseResult
from . import buckling

# EN 1993-1-8 bolt data: nominal d -> (hole d0 [mm], tensile area As [mm2])
BOLTS = {8: (9.0, 36.6), 10: (11.0, 58.0), 12: (13.0, 84.3),
         14: (15.0, 115.0), 16: (18.0, 157.0), 20: (22.0, 245.0),
         24: (26.0, 353.0)}
# grade -> (fub [MPa], alpha_v for shear through threads)
BOLT_GRADES = {"4.6": (400.0, 0.6), "4.8": (400.0, 0.5),
               "5.6": (500.0, 0.6), "5.8": (500.0, 0.5),
               "6.8": (600.0, 0.5), "8.8": (800.0, 0.6),
               "10.9": (1000.0, 0.5)}


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
            out += _brace_bolt_checks(model, case)
            out += _base_plate_checks(model, case)
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


def _fu_of(model: RackModel, sec: CrossSection) -> float:
    if sec.fu:
        return sec.fu
    return model.checks.fu_over_fy * model.materials[sec.material].fy


def _bearing(d: float, d0: float, fub: float, sec: CrossSection,
             fu: float, gamma_M2: float) -> float:
    """EN 1993-1-8 Table 3.4 bearing resistance of one ply [N]."""
    alpha_b = min(sec.e1 / (3.0 * d0), fub / fu, 1.0)
    k1 = min(2.8 * sec.e2 / d0 - 1.7, 2.5)
    return k1 * alpha_b * fu * d * sec.t / gamma_M2


def _brace_bolt_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    st = model.checks
    if st.bolt_d is None:
        return []
    d = float(st.bolt_d)
    if int(d) not in BOLTS or st.bolt_grade not in BOLT_GRADES:
        return [CheckResult("BRACE_BOLT", case.name, "settings", "-", 99.0,
                            f"unknown bolt M{d:.0f} grade {st.bolt_grade}")]
    d0, As = BOLTS[int(d)]
    fub, alpha_v = BOLT_GRADES[st.bolt_grade]
    Fv = alpha_v * fub * As / st.gamma_M2

    # node -> upright section, for the bearing on the connected upright
    upright_at: Dict[int, CrossSection] = {}
    for m in model.members.values():
        sec = model.section_of(m)
        if m.member_set == "uprights" or sec.role == "upright":
            upright_at.setdefault(m.node_i, sec)
            upright_at.setdefault(m.node_j, sec)

    res: List[CheckResult] = []
    missing = set()
    for mid, mr in case.members.items():
        m = model.members[mid]
        if m.member_set not in ("bracing", "row spacers"):
            continue
        brace = model.section_of(m)
        upright = upright_at.get(m.node_i) or upright_at.get(m.node_j)
        plies = [("brace", brace)] + ([("upright", upright)] if upright else [])
        if any(s.e1 is None or s.e2 is None or s.t is None for _, s in plies):
            missing.add(brace.name if brace.e1 is None or brace.t is None
                        else (upright.name if upright else "?"))
            continue
        parts = {"bolt shear": st.bolts_per_connection * Fv}
        for label, sec in plies:
            fu = _fu_of(model, sec)
            parts[f"bearing {label}"] = st.bolts_per_connection * _bearing(
                d, d0, fub, sec, fu, st.gamma_M2)
        gov_label, R = min(parts.items(), key=lambda kv: kv[1])
        N = max(abs(mr.N_min), abs(mr.N_max))
        res.append(CheckResult(
            "BRACE_BOLT", case.name, f"member {mid}", m.member_set, N / R,
            f"N={N/1e3:.2f} kN vs {st.bolts_per_connection}x M{d:.0f} "
            f"{st.bolt_grade}: " +
            ", ".join(f"{k}={v/1e3:.2f}" for k, v in parts.items()) +
            f" kN -> R={R/1e3:.2f} kN ({gov_label} governs)"))
    for name in sorted(missing):
        res.append(CheckResult(
            "BRACE_BOLT", case.name, f"section {name}", "-", 0.0,
            "e1/e2/thickness missing in the master - connection not checked",
            informative=True))
    return res


def _base_plate_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    bp = model.base_plate
    if bp is None or not case.reactions:
        return []
    f_jd = bp.bearing_strength()
    g0 = model.checks.gamma_M0

    # governing (most compressed) support and its upright footprint
    node, r = max(case.reactions.items(), key=lambda kv: kv[1][2])
    N = max(r[2], 0.0)
    foot_w = foot_d = None
    for m in model.members.values():
        if node in (m.node_i, m.node_j):
            sec = model.section_of(m)
            if m.member_set == "uprights" or sec.role == "upright":
                foot_w, foot_d = sec.depth_h, sec.width_b
                break
    note = ""
    if not foot_w or not foot_d:
        foot_w = foot_d = 100.0
        note = " (upright footprint unknown, 100x100 assumed)"

    # minimum required plate: footprint + uniform projection c so that
    # the bearing area carries N; thickness from the cantilever projection
    A_req = N / f_jd
    if A_req > foot_w * foot_d:
        s, p = foot_w + foot_d, A_req - foot_w * foot_d
        c_req = (-s + math.sqrt(s * s + 4.0 * p)) / 4.0
    else:
        c_req = 0.0
    t_req_min = c_req * math.sqrt(3.0 * f_jd * g0 / bp.fy_plate)
    min_txt = (f"min plate {foot_w + 2*c_req:.0f}x{foot_d + 2*c_req:.0f} mm, "
               f"t>={max(t_req_min, 4.0):.1f} mm "
               f"(N={N/1e3:.1f} kN at node {node}, f_jd={f_jd:.2f} MPa, "
               f"c={c_req:.1f} mm{note})")

    if bp.b and bp.d and bp.t:
        util_bearing = N / (bp.b * bp.d * f_jd)
        c_act = max((bp.b - foot_w) / 2.0, (bp.d - foot_d) / 2.0, 0.0)
        t_req = c_act * math.sqrt(3.0 * f_jd * g0 / bp.fy_plate)
        util_t = t_req / bp.t if bp.t > 0 else 99.0
        return [
            CheckResult("BASEPLATE", case.name, f"node {node} bearing", "-",
                        util_bearing,
                        f"N={N/1e3:.1f} kN vs {bp.b:.0f}x{bp.d:.0f} plate, "
                        f"f_jd={f_jd:.2f} MPa; {min_txt}"),
            CheckResult("BASEPLATE", case.name, f"node {node} thickness", "-",
                        util_t,
                        f"t={bp.t:.1f} mm vs required {t_req:.1f} mm "
                        f"(projection c={c_act:.1f} mm, fy={bp.fy_plate:.0f})"),
        ]
    return [CheckResult("BASEPLATE", case.name, f"node {node}", "-", 0.0,
                        min_txt, informative=True)]


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
