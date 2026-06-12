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
            out += _splice_checks(model, case)
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
    """Footplate per EN 1993-1-8 6.2.5 (T-stub in compression): the plate
    bears on STRIPS of width c on each side of the upright's walls,

        c = t_p * sqrt(fy_p / (3 * f_jd * gamma_M0)),
        A_eff = L_p * (t_wall + 2c)   (L_p = developed wall length = A/t),

    and must carry the governing base demand N_eq = N + 6*M/d (elastic
    peak-pressure equivalent of the concurrent base moment).  The required
    thickness follows from inverting c; typical rack plates of 3-4 mm
    verify."""
    bp = model.base_plate
    if bp is None or not case.reactions:
        return []
    f_jd = bp.bearing_strength()
    g0 = model.checks.gamma_M0

    # upright section at each support, for wall thickness / footprint
    def upright_at(node: int):
        for m in model.members.values():
            if node in (m.node_i, m.node_j):
                sec = model.section_of(m)
                if m.member_set == "uprights" or sec.role == "upright":
                    return sec
        return None

    # governing support: max equivalent axial incl. the base moment
    best = None
    for node, r in case.reactions.items():
        N = max(r[2], 0.0)
        M = math.hypot(r[3], r[4])
        sec = upright_at(node)
        d_h = (sec.depth_h if sec and sec.depth_h else 100.0)
        N_eq = N + 6.0 * M / d_h
        if best is None or N_eq > best[0]:
            best = (N_eq, N, M, node, sec)
    N_eq, N, M, node, sec = best

    note = ""
    if sec is None or not sec.t:
        sec_t, sec_A = 2.0, 600.0
        note = " (upright wall data missing in master, t=2/A=600 assumed)"
    else:
        sec_t, sec_A = sec.t, sec.A
    foot_w = sec.depth_h if sec and sec.depth_h else 100.0
    foot_d = sec.width_b if sec and sec.width_b else 100.0
    L_p = sec_A / sec_t                      # developed wall length

    A_req = N_eq / f_jd
    c_req = max(0.0, (A_req / L_p - sec_t) / 2.0)
    t_req = c_req * math.sqrt(3.0 * f_jd * g0 / bp.fy_plate)
    min_b = max(foot_w + 2.0 * c_req, math.sqrt(A_req * foot_w / foot_d))
    min_d = max(foot_d + 2.0 * c_req, A_req / min_b)
    min_txt = (f"N={N/1e3:.1f} kN, M={M/1e6:.2f} kNm -> N_eq={N_eq/1e3:.1f} kN "
               f"at node {node}; f_jd={f_jd:.2f} MPa, A_req={A_req:.0f} mm2, "
               f"strip c_req={c_req:.1f} mm -> t_req={t_req:.1f} mm "
               f"(use >= {max(t_req, 3.0):.1f} mm), "
               f"min plate {min_b:.0f}x{min_d:.0f} mm{note}")

    if bp.b and bp.d and bp.t:
        c_t = bp.t * math.sqrt(bp.fy_plate / (3.0 * f_jd * g0))
        A_eff = min(L_p * (sec_t + 2.0 * c_t), bp.b * bp.d)
        util = A_req / A_eff if A_eff > 0 else 99.0
        fit = ""
        if bp.b + 1.0 < foot_w or bp.d + 1.0 < foot_d:
            util = max(util, 99.0)
            fit = (f"; FAIL plate smaller than the upright footprint "
                   f"{foot_w:.0f}x{foot_d:.0f}")
        return [CheckResult(
            "BASEPLATE", case.name, f"node {node}", "-", util,
            f"plate {bp.b:.0f}x{bp.d:.0f}x{bp.t:.1f}: c={c_t:.1f} mm, "
            f"A_eff={A_eff:.0f} mm2 vs A_req={A_req:.0f} mm2; {min_txt}{fit}")]
    return [CheckResult("BASEPLATE", case.name, f"node {node}", "-", 0.0,
                        min_txt, informative=True)]


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


# ------------------------------------------------------------------ summary
def governing(checks: List[CheckResult]) -> Optional[CheckResult]:
    real = [c for c in checks if not c.informative]
    return max(real, key=lambda c: c.utilization) if real else None


def all_ok(checks: List[CheckResult]) -> bool:
    return all(c.ok for c in checks)
