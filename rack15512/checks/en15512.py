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
  BASEPLATE  footplate per EN 1993-1-8 6.2.5 (T-stub in compression): the
             plate bears on strips of width c = t*sqrt(fy/(3*f_jd*gM0))
             around the upright walls, A_eff = L_p*(t_wall + 2c) with
             L_p = developed wall length; demand N_eq = N + 6*M/d from the
             governing base reaction (axial + moment).  Required plate
             thickness and minimum plate size are reported; the actual
             plate is verified when given.  Enabled by RackModel.base_plate.
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

# Default characteristic resistances for mechanical (wedge / expansion)
# anchors in CRACKED C20/25, non-seismic.  These stand in for the product ETA
# values and are intentionally conservative; they are overridable per config
# (BasePlate.anchor_pullout_rk / anchor_shear_rk).  diameter [mm] -> R_k [N].
ANCHOR_PULLOUT_RK = {8: 6000.0, 10: 9000.0, 12: 12000.0,
                     16: 20000.0, 20: 30000.0}      # N_Rk,p  (legacy reference)
# default pull-out N_Rk,p = K_PULLOUT * hef[mm] * d[mm]  [N] — scales with the
# embedment depth (calibrated to the table above at the nominal hef ~ 6*d), so
# changing hef changes the pull-out capacity.
K_PULLOUT = 14.3
ANCHOR_SHEAR_RK_C = {8: 8000.0, 10: 12000.0, 12: 17000.0,
                     16: 30000.0, 20: 45000.0}      # V_Rk,c  (concrete shear)


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
            out += _brace_buckling_checks(model, case)
            out += _connector_checks(model, case)
            out += _brace_bolt_checks(model, case)
            out += _base_plate_checks(model, case)
            out += _base_restraint_checks(model, case)
            out += _anchorage_checks(model, case)
            out += _splice_checks(model, case)
            a = _alpha_cr_check(model, case)
            if a:
                out.append(a)
        elif case.kind == "SEISMIC":
            if getattr(case, "seismic_service", False):
                # unfactored 1.0(DL+EL) case: drift & P-Delta limits only
                # (IS 1893 Cl 7.11.1 - partial load factor 1.0)
                out += _seismic_drift_checks(model, case)
                out += _seismic_pdelta_checks(model, case)
            else:
                # factored ULS seismic combos: member strength only. Footplate
                # / anchor are NOT checked here - designed separately (anchor
                # designer) so anchorage never blocks the bracing design.
                out += _stress_checks(model, case)
                out += _buckling_checks(model, case)
                out += _brace_buckling_checks(model, case)
                out += _connector_checks(model, case)
                out += _brace_bolt_checks(model, case)
                out += _splice_checks(model, case)
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
        gov = "y" if chi_y <= chi_z else "z"
        # flexural-torsional buckling (EN 15512 9.7.5) when the gross
        # torsion / warping / shear-centre data is available
        ft_txt = ""
        # torsional restraint at the cross-aisle bracing nodes: the
        # torsional length is the bracing-node spacing (Lcr_z)
        L_tors = m.L_buckling_y or mr.length
        chi_ft = _chi_ft(sec, mat, L_tors, Ncr_y, model.checks.beta_T)
        if chi_ft is not None and chi_ft < chi_min:
            chi_min, gov = chi_ft, "FT"
            ft_txt = f", chi_FT={chi_ft:.3f}"
        Nb_rd = chi_min * sec.area_eff * mat.fy / g
        My_rd = sec.mod_y_eff * mat.fy / g
        Mz_rd = sec.mod_z_eff * mat.fy / g
        Nc = abs(mr.N_min)
        eta = Nc / Nb_rd
        if m.mtype == "beam":
            eta += kM * mr.My_absmax / My_rd + kM * mr.Mz_absmax / Mz_rd
        detail = (f"Nc={Nc/1e3:.1f} kN, My={mr.My_absmax/1e6:.2f} kNm, "
                  f"Mz={mr.Mz_absmax/1e6:.2f} kNm; "
                  f"Lcr_y={Lcr_y:.0f}, Lcr_z={Lcr_z:.0f} mm, "
                  f"lambda_y={lam_y:.2f}, lambda_z={lam_z:.2f}, "
                  f"chi_min={chi_min:.3f} (gov {gov}){ft_txt}, "
                  f"Nb_Rd={Nb_rd/1e3:.1f} kN")
        res.append(CheckResult("BUCKLING", case.name, f"member {mid}",
                               m.member_set, eta, detail))
    return res


def _chi_ft(sec: CrossSection, mat, length: float, Ncr_y: float,
            beta_T: float = 0.7) -> Optional[float]:
    """Flexural-torsional buckling reduction factor (EN 15512 9.7.5), or
    None when the gross torsion/warping/shear-centre data is unavailable.
    The torsional buckling length is beta_T * length (fig 24)."""
    if sec.It_gross is None or sec.Iw_gross is None or sec.y0 is None:
        return None
    Iy_g = sec.Iy_gross if sec.Iy_gross is not None else sec.Iy
    Iz_g = sec.Iz_gross if sec.Iz_gross is not None else sec.Iz
    A = sec.A
    i0_sq = (Iy_g + Iz_g) / A + sec.y0 ** 2
    L_T = beta_T * length
    Ncr_T = buckling.n_cr_torsional(mat.E, mat.G, sec.It_gross,
                                    sec.Iw_gross, i0_sq, L_T)
    Ncr_FT = buckling.n_cr_flex_tors(Ncr_y, Ncr_T, sec.y0, i0_sq)
    if Ncr_FT <= 0:
        return None
    lam = buckling.lambda_bar(sec.area_eff, mat.fy, Ncr_FT)
    return buckling.chi(lam, sec.buckling_curve_y)


def _brace_buckling_checks(model: RackModel,
                           case: CaseResult) -> List[CheckResult]:
    """Compression buckling of the frame-bracing members (EN 15512 10.4):
    flexural about both axes plus flexural-torsional, buckling curve from
    the bracing master (typically 'c'), system length = member length.
    Uses the FULL brace area (the 0.15 analysis factor models connection
    flexibility only, not a strength reduction)."""
    res = []
    g = model.checks.gamma_M1
    for mid, mr in case.members.items():
        m = model.members[mid]
        if m.member_set not in ("bracing", "row spacers", "plan bracing",
                                "spine bracing", "frame spacer"):
            continue
        if mr.N_min >= 0.0:
            continue
        sec = model.section_of(m)
        mat = model.material_of(m)
        L = mr.length
        Ncr_y = buckling.n_cr(mat.E, sec.Iy, L)
        Ncr_z = buckling.n_cr(mat.E, sec.Iz, L)
        chi_y = buckling.chi(buckling.lambda_bar(sec.A, mat.fy, Ncr_y),
                             sec.buckling_curve_y)
        chi_z = buckling.chi(buckling.lambda_bar(sec.A, mat.fy, Ncr_z),
                             sec.buckling_curve_z)
        chi_min, gov = (chi_y, "y") if chi_y <= chi_z else (chi_z, "z")
        chi_ft = _chi_ft(sec, mat, L, Ncr_y, beta_T=1.0)   # brace: betaT=1
        if chi_ft is not None and chi_ft < chi_min:
            chi_min, gov = chi_ft, "FT"
        Nb_rd = chi_min * sec.A * mat.fy / g
        Nc = abs(mr.N_min)
        res.append(CheckResult(
            "BRACE_BUCKLING", case.name, f"member {mid}", m.member_set,
            Nc / Nb_rd,
            f"Nc={Nc/1e3:.2f} kN, L={L:.0f} mm, chi_min={chi_min:.3f} "
            f"(gov {gov}, curve {sec.buckling_curve_z}), "
            f"Nb_Rd={Nb_rd/1e3:.2f} kN"))
    return res


def _connector_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    res = []
    for mid, mr in case.members.items():
        m = model.members[mid]
        sec = model.section_of(m)
        v_rd = sec.connector_v_rd
        a_arm = sec.connector_arm
        for end, hinge in (("i", m.hinge_i), ("j", m.hinge_j)):
            if hinge is None:
                continue
            st = mr.end(end)
            for axis, m_rd, M in (("z", hinge.m_rd_z, st.Mz),
                                  ("y", hinge.m_rd_y, st.My)):
                if m_rd is None:
                    continue
                # EN 15512 9.5.4 combined bending + shear at the connector:
                #   M_Sd/M_Rd + (V_Sd - M_Rd/a)/V_Rd <= 1
                # falls back to pure bending when V_Rd is not in the master
                V = math.hypot(st.Vy, st.Vz)
                if v_rd and axis == "z":
                    util = abs(M) / m_rd + max(V - m_rd / a_arm, 0.0) / v_rd
                    detail = (f"M{axis},Ed={abs(M)/1e6:.3f} kNm, "
                              f"V_Ed={V/1e3:.2f} kN; M_Rd={m_rd/1e6:.3f} kNm, "
                              f"V_Rd={v_rd/1e3:.2f} kN, a={a_arm:.0f} mm "
                              f"(EN 15512 9.5.4 interaction)")
                else:
                    util = abs(M) / m_rd
                    detail = (f"M{axis},Ed={abs(M)/1e6:.3f} kNm, "
                              f"M{axis},Rd={m_rd/1e6:.3f} kNm")
                res.append(CheckResult(
                    "CONNECTOR", case.name,
                    f"member {mid} end {end} ({axis})",
                    m.member_set, util, detail))
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
        if m.member_set not in ("bracing", "row spacers", "plan bracing",
                                "spine bracing", "frame spacer"):
            continue
        brace = model.section_of(m)
        upright = upright_at.get(m.node_i) or upright_at.get(m.node_j)
        plies = [("brace", brace)] + ([("upright", upright)] if upright else [])
        if any(s.e1 is None or s.e2 is None or s.t is None for _, s in plies):
            missing.add(brace.name if brace.e1 is None or brace.t is None
                        else (upright.name if upright else "?"))
            continue
        planes = max(int(getattr(st, "brace_planes", 1) or 1), 1)
        # n shear planes -> bolt shear x n; n brace plies -> brace bearing x n;
        # the upright (single wall) bearing is unchanged
        parts = {"bolt shear": st.bolts_per_connection * planes * Fv}
        for label, sec in plies:
            fu = _fu_of(model, sec)
            factor = planes if label == "brace" else 1
            parts[f"bearing {label}"] = st.bolts_per_connection * factor \
                * _bearing(d, d0, fub, sec, fu, st.gamma_M2)
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


def _upright_at(model: RackModel, node: int):
    for m in model.members.values():
        if node in (m.node_i, m.node_j):
            sec = model.section_of(m)
            if m.member_set == "uprights" or sec.role == "upright":
                return sec
    return None


def _base_plate_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    """Contact pressure on the floor + base plate (EN 15512 9.9 / 9.10.1,
    10.5.3/4): the upright compression spreads under the wall over a strip
    of half-width e = t_p*sqrt(fy_p/(3 fj)) (capped at the plate overhang),
    giving Abas = L_p*(t_wall + 2e) (<= plate area); check N_Sd <= fj*Abas.
    fj = 2.5*f_ck/gamma_c.  The base moment is NOT included here - it is the
    separate BASE_RESTRAINT check (EN 15512 10.5.1)."""
    bp = model.base_plate
    if bp is None or not case.reactions:
        return []
    fj = bp.bearing_strength()

    node, r = max(case.reactions.items(), key=lambda kv: kv[1][2])
    N = max(r[2], 0.0)
    sec = _upright_at(model, node)
    note = ""
    if sec is None or not sec.t:
        sec_t, sec_A, foot_w, foot_d = 2.0, 600.0, 100.0, 100.0
        note = " (upright data missing in master; t=2, A=600 assumed)"
    else:
        sec_t, sec_A = sec.t, sec.A
        foot_w = sec.depth_h or 100.0        # along X
        foot_d = sec.width_b or 100.0        # plate width, along Y
    L_p = sec_A / sec_t                       # developed wall length

    A_req = N / fj
    if bp.b and bp.d and bp.t:
        # overhang from the upright wall to the nearest plate edge caps e
        over_x = max((bp.b - foot_w) / 2.0, 0.0)
        over_y = max((bp.d - foot_d) / 2.0, 0.0)
        e_cap = max(min(over_x, over_y), 0.0) or max(over_x, over_y)
        e = bp.t * math.sqrt(bp.fy_plate / (3.0 * fj))
        e_eff = min(e, e_cap) if e_cap > 0 else e
        Abas = min(L_p * (sec_t + 2.0 * e_eff), bp.b * bp.d)
        util = A_req / Abas if Abas > 0 else 99.0
        # thickness needed so the strip reaches the plate edge (full Abas)
        t_min = (foot_w * 0.0)  # placeholder, computed from e_cap below
        t_for_edge = (e_cap / math.sqrt(bp.fy_plate / (3.0 * fj))
                      if e_cap > 0 else bp.t)
        detail = (f"N={N/1e3:.1f} kN at node {node}; fj=2.5*fck/gc="
                  f"{fj:.1f} MPa, plate {bp.b:.0f}x{bp.d:.0f}x{bp.t:.1f}, "
                  f"e={e:.1f} mm (cap {e_cap:.1f}), Abas={Abas:.0f} mm2, "
                  f"fj*Abas={fj*Abas/1e3:.1f} kN >= N? "
                  f"util={util:.3f}; t to fill plate ~{t_for_edge:.1f} mm"
                  f"{note}")
        return [CheckResult("BASEPLATE", case.name, f"node {node}", "-",
                            util, detail)]
    # no plate given: report the minimum bearing area needed
    return [CheckResult(
        "BASEPLATE", case.name, f"node {node}", "-", 0.0,
        f"N={N/1e3:.1f} kN, fj={fj:.1f} MPa -> min contact area "
        f"Abas={A_req:.0f} mm2; a standard footplate (3-4 mm) normally "
        f"suffices{note}", informative=True)]


def _base_restraint_checks(model: RackModel,
                           case: CaseResult) -> List[CheckResult]:
    """Partial restraint of the upright base (EN 15512 10.5.1):
    MSd,y / MRd(NSd) <= 1, with MRd(NSd) interpolated from the
    floor-connection moment-resistance table (BASE_STIFFNESS sheet)."""
    bp = model.base_plate
    if bp is None or not bp.m_rd_n or not case.reactions:
        return []
    res = []
    worst = None
    for node, r in case.reactions.items():
        N = max(r[2], 0.0)
        M = math.hypot(r[3], r[4])           # base restraint moment
        m_rd = bp.m_rd_at(N)
        if not m_rd:
            continue
        util = M / m_rd
        if worst is None or util > worst.utilization:
            worst = CheckResult(
                "BASE_RESTRAINT", case.name, f"node {node}", "uprights",
                util, f"N={N/1e3:.1f} kN, M_Sd={M/1e6:.2f} kNm, "
                      f"M_Rd(N)={m_rd/1e6:.2f} kNm")
    if worst:
        res.append(worst)
    return res


def _anchor_grade_fu_fy(grade: str) -> Tuple[float, float]:
    """(f_uk, f_yk) [MPa] from an ISO bolt grade string 'X.Y'."""
    a, b = grade.split(".")
    fuk = float(a) * 100.0
    fyk = float(a) * float(b) * 10.0
    return fuk, fyk


def _anchor_capacities(bp) -> Optional[dict]:
    """Per-anchor design resistances for a wedge anchor to EN 1992-4
    (non-seismic), returning N_Rd by failure mode and V_Rd by failure mode.
    Returns None when the anchor diameter / grade are unknown."""
    d = int(round(bp.anchor_d))
    if d not in BOLTS or bp.anchor_grade not in BOLT_GRADES:
        return None
    _, As = BOLTS[d]
    fuk, fyk = _anchor_grade_fu_fy(bp.anchor_grade)
    g_n = bp.gamma_ms_n if bp.gamma_ms_n else max(1.2 * fuk / fyk, 1.4)
    g_v = bp.gamma_ms_v if bp.gamma_ms_v else max(1.0 * fuk / fyk, 1.25)
    gc = bp.gamma_mc or 1.5
    hef = bp.anchor_hef
    fck = bp.f_ck

    # --- tension limit states ------------------------------------------
    n_rd_s = As * fuk / g_n                                   # steel
    # pull-out default scales with embedment x diameter (K_PULLOUT calibrated
    # so the previous per-diameter table is reproduced at the nominal hef);
    # this makes the embedment depth influence the result. Override wins.
    n_rk_p = bp.anchor_pullout_rk or (K_PULLOUT * hef * d)
    n_rd_p = n_rk_p / gc                                      # pull-out
    # concrete cone (EN 1992-4 7.2.1.4), cracked k1=7.7, simplified group /
    # edge factors for the 2-anchor footplate (no concrete geometry modelled)
    n_rk_c0 = 7.7 * math.sqrt(fck) * hef ** 1.5
    s_cr = 3.0 * hef
    s = (bp.anchor_spacing if bp.anchor_spacing
         else (max(bp.d - 60.0, 0.5 * bp.d) if bp.d else 100.0))
    grp = 0.5 * (1.0 + min(s, s_cr) / s_cr)                   # group sharing
    psi_ed = 1.0
    if bp.anchor_edge and bp.anchor_edge < 1.5 * hef:
        psi_ed = 0.7 + 0.3 * bp.anchor_edge / (1.5 * hef)
    n_rd_c = n_rk_c0 * grp * psi_ed / gc                      # cone

    # --- shear limit states --------------------------------------------
    v_rd_s = 0.5 * As * fuk / g_v                             # steel (k6=0.5)
    v_rk_c = bp.anchor_shear_rk or ANCHOR_SHEAR_RK_C.get(
        d, ANCHOR_SHEAR_RK_C[12])
    v_rd_c = v_rk_c / gc                                      # concrete
    return {"n_rd_s": n_rd_s, "n_rd_p": n_rd_p, "n_rd_c": n_rd_c,
            "v_rd_s": v_rd_s, "v_rd_c": v_rd_c,
            "n_rd": min(n_rd_s, n_rd_p, n_rd_c),
            "v_rd": min(v_rd_s, v_rd_c), "s": s}


def _anchorage_checks(model: RackModel,
                      case: CaseResult) -> List[CheckResult]:
    """Wedge-anchor design of the footplate to EN 1992-4 (non-seismic),
    Profis-Hilti style: per anchor the tension demand (uplift / n + base
    moment / lever) is verified against min(steel, pull-out, concrete cone)
    and the shear demand (base shear / n) against min(steel, concrete);
    combined via (beta_N)^1.5 + (beta_V)^1.5 <= 1 (EN 1992-4 7.2.3).  The
    EN 15512 9.10.4 minimum (3 kN tension + 5 kN shear capacity per
    connection) is enforced as a floor."""
    bp = model.base_plate
    if bp is None or not case.reactions:
        return []
    cap = _anchor_capacities(bp)
    if cap is None:
        return [CheckResult(
            "ANCHORAGE", case.name, "settings", "uprights", 99.0,
            f"unknown anchor M{bp.anchor_d:.0f} grade {bp.anchor_grade}")]
    n = max(int(bp.n_anchors), 1)
    n_rd, v_rd, s = cap["n_rd"], cap["v_rd"], cap["s"]

    worst = None
    for node, r in case.reactions.items():
        uplift = max(-r[2], 0.0)
        M = math.hypot(r[3], r[4])
        V = math.hypot(r[0], r[1])
        n_ed = uplift / n + (M / s if s > 0 else 0.0)        # per tension anchor
        v_ed = V / n                                          # per anchor
        bN = n_ed / n_rd if n_rd > 0 else 99.0
        bV = v_ed / v_rd if v_rd > 0 else 99.0
        comb = (min(bN, 1.0) ** 1.5 + min(bV, 1.0) ** 1.5
                if bN <= 1.0 and bV <= 1.0 else bN ** 1.5 + bV ** 1.5)
        util = max(bN, bV, comb)
        if worst is None or util > worst[0]:
            worst = (util, node, n_ed, v_ed, bN, bV, comb)

    util, node, n_ed, v_ed, bN, bV, comb = worst
    floor = ""
    if n_rd < bp.anchor_tension or v_rd < bp.anchor_shear:
        floor = (f"; below EN 15512 9.10.4 minimum "
                 f"({bp.anchor_tension/1e3:.0f} kN tension / "
                 f"{bp.anchor_shear/1e3:.0f} kN shear)")
        util = max(util, bp.anchor_tension / n_rd if n_rd else 99.0,
                   bp.anchor_shear / v_rd if v_rd else 99.0)
    detail = (
        f"{n}x M{bp.anchor_d:.0f} {bp.anchor_grade} wedge, hef="
        f"{bp.anchor_hef:.0f} mm, s={s:.0f} mm; per anchor N_Ed="
        f"{n_ed/1e3:.2f} kN, V_Ed={v_ed/1e3:.2f} kN. "
        f"Tension N_Rd=min(steel {cap['n_rd_s']/1e3:.1f}, pull-out "
        f"{cap['n_rd_p']/1e3:.1f}, cone {cap['n_rd_c']/1e3:.1f})="
        f"{n_rd/1e3:.1f} kN (betaN={bN:.2f}); Shear V_Rd=min(steel "
        f"{cap['v_rd_s']/1e3:.1f}, concrete {cap['v_rd_c']/1e3:.1f})="
        f"{v_rd/1e3:.1f} kN (betaV={bV:.2f}); combined "
        f"betaN^1.5+betaV^1.5={comb:.2f}{floor}")
    return [CheckResult("ANCHORAGE", case.name, f"node {node}", "uprights",
                        util, detail)]


def _splice_checks(model: RackModel, case: CaseResult) -> List[CheckResult]:
    """Upright splice connection per EN 1993-1-8: elastic bolt-group method
    for the concurrent N, V (resultant) and M (resultant) at the splice
    elevation; per-bolt resistance = min(shear, bearing) with bearing on
    the lesser of the upright wall and the sleeve thickness."""
    res: List[CheckResult] = []
    for sp in model.splices:
        if int(sp.bolt_d) not in BOLTS or sp.bolt_grade not in BOLT_GRADES:
            res.append(CheckResult("SPLICE", case.name, f"z={sp.z:.0f}", "-",
                                   99.0, f"unknown bolt M{sp.bolt_d:.0f} "
                                         f"grade {sp.bolt_grade}"))
            continue
        d0, As = BOLTS[int(sp.bolt_d)]
        fub, alpha_v = BOLT_GRADES[sp.bolt_grade]
        g2 = model.checks.gamma_M2
        Fv = alpha_v * fub * As / g2

        # bolt-group geometry (one side), elastic method
        n = sp.rows * sp.cols
        coords = [((r - (sp.rows - 1) / 2.0) * sp.p1,
                   (c - (sp.cols - 1) / 2.0) * sp.p2)
                  for r in range(sp.rows) for c in range(sp.cols)]
        sum_r2 = sum(x * x + y * y for x, y in coords)

        worst: Optional[Tuple[float, str, int]] = None
        for mid, mr in case.members.items():
            m = model.members[mid]
            sec = model.section_of(m)
            if not (m.member_set == "uprights" or sec.role == "upright"):
                continue
            zi = model.nodes[m.node_i].z
            zj = model.nodes[m.node_j].z
            if abs(zi - sp.z) <= 1.0:
                st = mr.stations[0]
            elif abs(zj - sp.z) <= 1.0 and zi < zj:
                continue        # counted once via the segment above
            else:
                continue
            N, V = abs(st.N), math.hypot(st.Vy, st.Vz)
            M = math.hypot(st.My, st.Mz)

            if sum_r2 > 1.0e-9:
                F = max(math.hypot(N / n + M * abs(y) / sum_r2,
                                   V / n + M * abs(x) / sum_r2)
                        for x, y in coords)
                m_note = ""
            else:
                F = math.hypot(N / n, V / n)
                if M > 1.0e4:    # a single bolt cannot carry the moment
                    F = max(F, 99.0 * Fv)
                    m_note = (f"; FAIL: single-bolt group cannot carry "
                              f"M={M/1e6:.2f} kNm - use rows/cols > 1")
                else:
                    m_note = ""

            t_eff = min(sec.t or 1.0e9, sp.t_sleeve or 1.0e9)
            if t_eff > 1.0e8:
                res.append(CheckResult(
                    "SPLICE", case.name, f"z={sp.z:.0f}", "-", 0.0,
                    "upright wall thickness missing in the master - "
                    "bearing not checked", informative=True))
                break
            fu = _fu_of(model, sec)
            alpha_b = min(sp.e1 / (3.0 * d0), fub / fu, 1.0)
            if sp.rows > 1 and sp.p1 > 0:
                alpha_b = min(alpha_b, sp.p1 / (3.0 * d0) - 0.25)
            k1 = min(2.8 * sp.e2 / d0 - 1.7, 2.5)
            if sp.cols > 1 and sp.p2 > 0:
                k1 = min(k1, 1.4 * sp.p2 / d0 - 1.7)
            Fb = k1 * alpha_b * fu * sp.bolt_d * t_eff / g2
            R = min(Fv, Fb)
            gov = "bolt shear" if Fv <= Fb else f"bearing (t={t_eff:.1f} mm)"
            util = F / R
            detail = (f"N={N/1e3:.1f} kN, V={V/1e3:.2f} kN, "
                      f"M={M/1e6:.2f} kNm -> F_bolt={F/1e3:.2f} kN vs "
                      f"{sp.rows}x{sp.cols} M{sp.bolt_d:.0f} "
                      f"{sp.bolt_grade}/side: Fv={Fv/1e3:.2f}, "
                      f"Fb={Fb/1e3:.2f} kN ({gov} governs){m_note}")
            if worst is None or util > worst[0]:
                worst = (util, detail, mid)
        if worst is not None:
            res.append(CheckResult(
                "SPLICE", case.name, f"member {worst[2]} (z={sp.z:.0f})",
                "uprights", worst[0], worst[1]))
    return res


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


# ------------------------------------------------------------------ seismic
def _storey_levels(model: RackModel) -> List[float]:
    from ..seismic import beam_storey_levels
    return beam_storey_levels(model)


def _seismic_drift_checks(model: RackModel,
                          case: CaseResult) -> List[CheckResult]:
    """Inter-storey drift ratio <= 0.004 (IS 1893 Cl 7.11.1)."""
    s = model.seismic
    limit = (s.drift_limit_ratio if s else 0.004)
    res = []
    drifts = case.seismic_storey_drift
    levels = _storey_levels(model)
    for lo, hi in zip(levels, levels[1:]):
        h = hi - lo
        if h <= 1e-6:
            continue
        d = drifts.get(round(hi, 3), drifts.get(hi, 0.0))
        ratio = d / h
        res.append(CheckResult(
            "SEISMIC_DRIFT", case.name, f"storey z={lo:.0f}-{hi:.0f}", "frame",
            ratio / limit,
            f"drift={d:.2f} mm over h={h:.0f} mm -> {ratio:.4f} "
            f"(limit {limit}); inter-storey, IS 1893 Cl 7.11.1 / EN 1998-1 "
            "4.4.3"))
    # informative overall (roof) drift = top displacement / total height
    if len(levels) >= 2:
        H = levels[-1] - levels[0]
        top = max((math.hypot(d[0], d[1])
                   for n, d in case.displacements.items()
                   if abs(model.nodes[n].z - levels[-1]) < 1.0), default=0.0)
        if H > 0:
            res.append(CheckResult(
                "SEISMIC_DRIFT", case.name, "overall (roof)", "frame",
                (top / H) / limit,
                f"top sway={top:.2f} mm over H={H:.0f} mm -> {top/H:.4f} "
                "(overall, informative)", informative=True))
    return res


def _seismic_pdelta_checks(model: RackModel,
                           case: CaseResult) -> List[CheckResult]:
    """P-Delta stability coefficient theta = P*Delta/(V*h) per storey.

    theta<=0.10 -> P-Delta negligible (informative); 0.10<theta<=0.25 -> the
    seismic forces should be amplified by 1/(1-theta); theta>0.25 -> fail."""
    s = model.seismic
    cap = s.theta_limit if s else 0.10
    levels = _storey_levels(model)
    z_min = levels[0]
    # total seismic weight above each level, from the lumped node weights
    from ..seismic import _node_weights
    try:
        weights = _node_weights(model, s) if s else {}
    except Exception:
        weights = {}
    Vb = 0.0
    if model.seismic_summary:
        Vb = max(model.seismic_summary.get("base_shear_x_kN", 0.0),
                 model.seismic_summary.get("base_shear_y_kN", 0.0)) * 1e3
    res = []
    for lo, hi in zip(levels, levels[1:]):
        h = hi - lo
        if h <= 1e-6:
            continue
        P = sum(w for nid, w in weights.items()
                if model.nodes[nid].z >= hi - 1e-6)
        # storey shear approximated as the share of base shear above this level
        Wabove = P
        Wtot = sum(weights.values()) or 1.0
        V = Vb * (Wabove / Wtot) if Vb else 0.0
        d = case.seismic_storey_drift.get(round(hi, 3),
                                          case.seismic_storey_drift.get(hi, 0.0))
        theta = (P * d) / (V * h) if V > 1e-9 else 0.0
        res.append(CheckResult(
            "SEISMIC_PDELTA", case.name, f"storey z={lo:.0f}-{hi:.0f}", "frame",
            theta / 0.25,
            f"theta={theta:.3f} (P={P/1e3:.0f} kN, V={V/1e3:.0f} kN, "
            f"delta={d:.2f} mm, h={h:.0f} mm); <=0.10 P-Delta negligible, "
            f">0.25 fails", informative=(theta <= cap)))
    return res


# ------------------------------------------------------------------ summary
def governing(checks: List[CheckResult]) -> Optional[CheckResult]:
    real = [c for c in checks if not c.informative]
    return max(real, key=lambda c: c.utilization) if real else None


def all_ok(checks: List[CheckResult]) -> bool:
    return all(c.ok for c in checks)
