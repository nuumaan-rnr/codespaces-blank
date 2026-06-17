"""IS 1893:2016 seismic design — modal Response Spectrum Analysis (RSA).

The strategy reuses the existing static engine: build the model once with
lumped mass and run ``eigen`` (engine.modal) for periods + mode shapes, run
each mode's equivalent static force through the ordinary ``run_case`` to recover
full internal forces, SRSS/CQC-combine the per-mode responses into a positive
(sign-less) envelope per direction, and finally superpose gravity ± seismic at
the response level into signed ``CaseResult`` objects with ``kind='SEISMIC'`` so
the existing EN/IS checks run unchanged.

Units: the engine works in N, mm.  Lumped mass for ``ops.mass`` is in
N·s²/mm ( = weight_N / G_MM, G_MM = 9806.65 mm/s² ), which yields periods in
seconds.  Modal forces are derived in weight terms (N) and are independent of
the mass unit (the participation factor cancels it), so only the periods depend
on G_MM.
"""

from __future__ import annotations

import math
from typing import Dict, List, Tuple

from .combos import AssembledLoads, assemble
from .model import Combination, RackModel
from .results import CaseResult, MemberResult, SeismicEnvelope, Station

G_MM = 9806.65                       # gravity [mm/s²]  (1 N = 1000 kg·mm/s²)
RHO_STEEL = 7.85e-6                   # steel density [tonne/mm³] = kg/mm³*... (see below)
# NB: A[mm²]·L[mm]·RHO gives kg when RHO=7.85e-6 kg/mm³; converted to weight by *G_MM/1000.

ZONE_FACTORS = {"II": 0.10, "III": 0.16, "IV": 0.24, "V": 0.36}   # Table 3

# Lateral-load-resisting system -> default response reduction factor R
# (IS 1893:2016 Table 9; rack-specific entries follow FEM 10.2.08 practice).
# Value None => the user sets R manually.
STRUCTURE_TYPES = {
    "Storage rack - cross-aisle braced": 4.0,
    "Storage rack - down-aisle moment frame": 3.0,
    "Steel OCBF (ordinary concentric braced)": 4.0,
    "Steel SCBF (special concentric braced)": 4.5,
    "Steel EBF (eccentric braced)": 5.0,
    "Steel OMRF (ordinary moment frame)": 3.0,
    "Steel SMRF (special moment frame)": 5.0,
    "Custom (set R manually)": None,
}

# Candidate spine/plan brace sections (lipped C family), lightest -> heaviest.
SPINE_CANDIDATES = ["1C36x21x6x1.2", "1C36x21x7x1.5", "1C60x40x10x1.6",
                    "1C60x40x10x2.0", "1C60x40x12x2.5", "1C80x40x10x1.6"]

# soil -> (plateau end T [s], decay numerator) for Sa/g (Cl 6.4.2, 5% damping)
_SOIL = {"I": (0.40, 1.00), "II": (0.55, 1.36), "III": (0.67, 1.67)}


# --------------------------------------------------------------------- spectrum
def design_spectrum_sa_g(T: float, soil: str) -> float:
    """IS 1893:2016 Cl 6.4.2 design acceleration spectrum Sa/g (5% damping)."""
    t_plateau, num = _SOIL.get(soil, _SOIL["II"])
    T = max(0.0, min(T, 4.0))
    if T < 0.10:
        return 1.0 + 15.0 * T
    if T <= t_plateau:
        return 2.50
    return num / T


def damping_correction(zeta: float) -> float:
    """EN 1998-1 damping correction factor eta = sqrt(10/(5+xi)), xi in %,
    floored at 0.55.  zeta is the viscous damping ratio (e.g. 0.05)."""
    import math
    xi = max(0.0, zeta) * 100.0
    return max(0.55, math.sqrt(10.0 / (5.0 + xi)))


def horizontal_seismic_coefficient(T: float, s) -> float:
    """Design horizontal seismic coefficient Ah = (Z/2)(I/R)(Sa/g), with the
    EN 16681 / FEM 10.2.08 spectrum-modification factor E_D2 applied (energy
    dissipation / damping of the loaded rack; <= 1.0)."""
    Z = ZONE_FACTORS.get(s.zone, 0.16)
    ed2 = max(0.55, min(1.0, getattr(s, "ed2", 1.0) or 1.0))
    return (Z / 2.0) * (s.importance / s.response_reduction) \
        * design_spectrum_sa_g(T, s.soil_type) * ed2


# --------------------------------------------------------------------- weights
def _node_weights(model: RackModel, s) -> Dict[int, float]:
    """Seismic weight [N] lumped at the real model nodes: dead +
    imposed_factor·pallets (+ member self-weight), excluding supported nodes."""
    W: Dict[int, float] = {}
    supported = {sup.node for sup in model.supports}

    def add(nid: int, w: float) -> None:
        if nid not in supported and w > 0.0:
            W[nid] = W.get(nid, 0.0) + w

    def case_factor(name: str) -> float:
        if name == "dead":
            return 1.0
        if name == "pallets":
            return s.imposed_factor
        return 0.0

    for name, lc in model.load_cases.items():
        f = case_factor(name)
        if f == 0.0:
            continue
        for nl in lc.nodal_loads:
            if nl.fz < 0.0:
                add(nl.node, f * abs(nl.fz))
        for ml in lc.member_loads:
            if ml.qz < 0.0:
                m = model.members[ml.member]
                w = f * abs(ml.qz) * model.member_length(m)
                add(m.node_i, w / 2.0)
                add(m.node_j, w / 2.0)
    if s.include_self_mass:
        for m in model.members.values():
            sec = model.sections.get(m.section)
            if not sec:
                continue
            # weight [N] = A[mm²]·L[mm]·rho[kg/mm³]·g  (g in m/s² -> /1000 of G_MM)
            w = sec.A * model.member_length(m) * RHO_STEEL * (G_MM / 1000.0)
            add(m.node_i, w / 2.0)
            add(m.node_j, w / 2.0)
    return W


def assemble_seismic_masses(model: RackModel, s) -> Dict[int, float]:
    """Lumped translational mass [N·s²/mm] for ops.mass (weight / G_MM)."""
    return {nid: w / G_MM for nid, w in _node_weights(model, s).items()}


# ------------------------------------------------------------- modal participation
def _participation(weights: Dict[int, float], shapes, k: int, comp: int
                   ) -> Tuple[float, float]:
    """(Gamma_W, W_eff) for mode k, direction comp (0=X,1=Y), in weight terms."""
    num = den = 0.0
    for nid, w in weights.items():
        phi = shapes.get(nid, [(0, 0, 0)])[k][comp]
        num += w * phi
        den += w * phi * phi
    if abs(den) < 1e-30:
        return 0.0, 0.0
    return num / den, (num * num) / den


def modal_force_loads(model, weights, shapes, k, comp, Ah) -> AssembledLoads:
    """Equivalent static modal force vector for mode k, one direction."""
    gamma, _ = _participation(weights, shapes, k, comp)
    out = AssembledLoads()
    for nid, w in weights.items():
        phi = shapes.get(nid, [(0, 0, 0)])[k][comp]
        f = Ah * gamma * w * phi
        if comp == 0:
            out.add_nodal(nid, f, 0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            out.add_nodal(nid, 0.0, f, 0.0, 0.0, 0.0, 0.0)
    return out


# ------------------------------------------------------------------- combination
def _cqc_rho(Ti: float, Tj: float, zeta: float) -> float:
    if Ti <= 0 or Tj <= 0:
        return 1.0 if Ti == Tj else 0.0
    beta = Tj / Ti
    den = (1 - beta ** 2) ** 2 + 4 * zeta ** 2 * beta * (1 + beta) ** 2
    return 8 * zeta ** 2 * (1 + beta) * beta ** 1.5 / den if den else 0.0


def _combine(values: List[float], periods: List[float], s) -> float:
    """SRSS or CQC of per-mode (signed) modal responses -> positive scalar."""
    if s.combination.upper() == "CQC":
        tot = 0.0
        for i, vi in enumerate(values):
            for j, vj in enumerate(values):
                tot += _cqc_rho(periods[i], periods[j], s.damping) * vi * vj
        return math.sqrt(max(tot, 0.0))
    return math.sqrt(sum(v * v for v in values))


def srss_envelope(per_mode: List[CaseResult], periods: List[float],
                  direction: str, s) -> SeismicEnvelope:
    """Combine per-mode CaseResults (one per mode, same direction) into a
    positive-only response envelope."""
    env = SeismicEnvelope(direction=direction)
    ref = per_mode[0]
    for mid, mr0 in ref.members.items():
        forces, defls = [], []
        for j in range(len(mr0.stations)):
            comps = []
            for ci, attr in enumerate(("N", "Vy", "Vz", "T", "My", "Mz")):
                vals = [getattr(cm.members[mid].stations[j], attr)
                        for cm in per_mode]
                comps.append(_combine(vals, periods, s))
            forces.append(tuple(comps))
            dy = _combine([cm.members[mid].stations[j].defl_y
                           for cm in per_mode], periods, s)
            dz = _combine([cm.members[mid].stations[j].defl_z
                           for cm in per_mode], periods, s)
            defls.append((dy, dz))
        env.member_force[mid] = forces
        env.member_defl[mid] = defls
        env.member_x[mid] = [st.x for st in mr0.stations]
    for nid in ref.reactions:
        env.reaction[nid] = tuple(
            _combine([cm.reactions[nid][c] for cm in per_mode], periods, s)
            for c in range(6))
    for nid in ref.displacements:
        env.displacement[nid] = tuple(
            _combine([cm.displacements[nid][c] for cm in per_mode], periods, s)
            for c in range(6))
    return env


# ------------------------------------------------------------------- base shear
def empirical_period(model: RackModel, direction: str) -> float:
    """Approximate empirical period (Cl 7.6) for ELF / base-shear scaling."""
    h = model.height() / 1000.0                       # m
    if direction == "X":                              # down-aisle moment frame
        return 0.085 * h ** 0.75
    ys = [n.y for n in model.nodes.values()]          # cross-aisle, braced
    d = max(0.5, (max(ys) - min(ys)) / 1000.0)
    return 0.09 * h / math.sqrt(d)


def _scale_to_static(env, model, weights, shapes, periods, s, comp,
                     total_W) -> None:
    """Record dynamic vs static base shear; scale up only when enabled.

    IS 1893 Cl 7.7.3 lets the dynamic (modal RSA) base shear be scaled up to
    the empirical-period static base shear ``V_static``.  We always compute and
    record both ``v_dyn`` and ``v_static`` (so the report can show the saving),
    but only apply the scale factor when ``apply_base_shear_scaling`` is set.
    """
    v_dyn_sq = 0.0
    for k, Tk in enumerate(periods):
        Ah = horizontal_seismic_coefficient(Tk, s)
        _, w_eff = _participation(weights, shapes, k, comp)
        v_dyn_sq += (Ah * w_eff) ** 2
    v_dyn = math.sqrt(v_dyn_sq)
    direction = "X" if comp == 0 else "Y"
    t_emp = empirical_period(model, direction)   # uses the full rack height
    v_static = horizontal_seismic_coefficient(t_emp, s) * total_W
    if s.apply_base_shear_scaling:
        lam = max(1.0, v_static / v_dyn) if v_dyn > 1e-9 else 1.0
        env.base_shear = max(v_dyn, v_static)
    else:                                   # use the modal-period base shear
        lam = 1.0
        env.base_shear = v_dyn
    env.scale, env.v_dyn, env.v_static, env.t_emp = lam, v_dyn, v_static, t_emp
    if lam != 1.0:
        _apply_scale(env, lam)


def _apply_scale(env: SeismicEnvelope, lam: float) -> None:
    for mid in env.member_force:
        env.member_force[mid] = [tuple(c * lam for c in f)
                                 for f in env.member_force[mid]]
        env.member_defl[mid] = [(a * lam, b * lam)
                                for a, b in env.member_defl[mid]]
    env.reaction = {n: tuple(c * lam for c in r)
                    for n, r in env.reaction.items()}
    env.displacement = {n: tuple(c * lam for c in d)
                        for n, d in env.displacement.items()}


def _pallet_live_weight(model: RackModel, s) -> float:
    """Seismic weight [N] contributed by the pallet (live) load only."""
    lc = model.load_cases.get("pallets")
    if not lc:
        return 0.0
    supported = {sup.node for sup in model.supports}
    f = s.imposed_factor
    tot = 0.0
    for nl in lc.nodal_loads:
        if nl.fz < 0.0 and nl.node not in supported:
            tot += f * abs(nl.fz)
    for ml in lc.member_loads:
        if ml.qz < 0.0:
            m = model.members[ml.member]
            tot += f * abs(ml.qz) * model.member_length(m)
    return tot


def _apply_pallet_sliding(env: SeismicEnvelope, model: RackModel, s,
                          total_W: float) -> None:
    """EN 16681 unit-load sliding: cap the horizontal force the pallet (live)
    mass transfers at ~ c_mu_h*mu*W_pallet.  The unit load slides on the ACTUAL
    (elastic) acceleration it feels at the beam - the behaviour factor R reduces
    the steel frame's design forces, not the pallet-to-beam friction interface -
    so the friction cap is compared against the un-reduced Ah*R.  When it binds,
    scale the envelope by the weight-averaged reduction
    f_pallet*(cap/Ah_el)+(1-f_pallet) (the structure dead mass is not capped)."""
    env.sliding_scale = 1.0
    if not getattr(s, "pallet_sliding", False) or total_W <= 0.0:
        return
    cap = s.c_mu_h * s.pallet_mu
    t = getattr(env, "t_emp", 0.0) or 0.0
    ah = horizontal_seismic_coefficient(t if t > 0 else 0.30, s)
    ah_el = ah * max(s.response_reduction, 1.0)      # un-reduce by R (elastic)
    if ah_el <= 0.0 or cap >= ah_el:
        return                              # friction >= demand: no sliding
    f_pallet = _pallet_live_weight(model, s) / total_W
    scale = f_pallet * (cap / ah_el) + (1.0 - f_pallet)
    env.sliding_scale = scale
    env.base_shear *= scale
    _apply_scale(env, scale)


# ----------------------------------------------------------- directional combine
def _directional(ex: SeismicEnvelope, ey: SeismicEnvelope
                 ) -> Dict[str, object]:
    """100% + 30% directional combination (Cl 6.3.4.1) -> positive magnitudes.

    Returns a dict mirroring the envelope fields with the per-component
    max(1.0|X|+0.3|Y|, 0.3|X|+1.0|Y|)."""
    def comb(a: float, b: float) -> float:
        return max(abs(a) + 0.3 * abs(b), 0.3 * abs(a) + abs(b))

    out = {"member_force": {}, "member_defl": {}, "member_x": {},
           "reaction": {}, "displacement": {}}
    for mid in ex.member_force:
        fx, fy = ex.member_force[mid], ey.member_force[mid]
        out["member_force"][mid] = [tuple(comb(fx[j][c], fy[j][c])
                                          for c in range(6))
                                    for j in range(len(fx))]
        dx, dy = ex.member_defl[mid], ey.member_defl[mid]
        out["member_defl"][mid] = [(comb(dx[j][0], dy[j][0]),
                                    comb(dx[j][1], dy[j][1]))
                                   for j in range(len(dx))]
        out["member_x"][mid] = ex.member_x.get(mid, [])
    for nid in ex.reaction:
        out["reaction"][nid] = tuple(comb(ex.reaction[nid][c],
                                          ey.reaction[nid][c])
                                     for c in range(6))
    for nid in ex.displacement:
        out["displacement"][nid] = tuple(comb(ex.displacement[nid][c],
                                              ey.displacement[nid][c])
                                         for c in range(6))
    return out


# --------------------------------------------------------------- superposition
def superpose_seismic_cases(case_grav: CaseResult, E: Dict[str, object],
                            model: RackModel, combo_row, s,
                            service: bool = False) -> List[CaseResult]:
    """Gravity ± seismic at the response level -> two signed SEISMIC cases.
    ``service=True`` marks the unfactored 1.0(DL+EL) case used for the drift /
    P-Delta limit checks."""
    label, _f_d, _f_il, f_el = combo_row
    out: List[CaseResult] = []
    for sign in (+1.0, -1.0):
        sgn = "+E" if sign > 0 else "-E"
        cr = CaseResult(name=f"SEIS {label} {sgn}", combo=label,
                        kind="SEISMIC", order=1, converged=True,
                        seismic_service=service)
        for mid, mr_g in case_grav.members.items():
            env_f = E["member_force"].get(mid)
            env_d = E["member_defl"].get(mid)
            env_x = E["member_x"].get(mid)
            stations = []
            for j, st in enumerate(mr_g.stations):
                ef = _interp(env_x, env_f, st.x) if env_f else (0,) * 6
                ed = _interp(env_x, env_d, st.x) if env_d else (0, 0)
                stations.append(Station(
                    x=st.x,
                    N=st.N + sign * f_el * ef[0],
                    Vy=st.Vy + sign * f_el * ef[1],
                    Vz=st.Vz + sign * f_el * ef[2],
                    T=st.T + sign * f_el * ef[3],
                    My=st.My + sign * f_el * ef[4],
                    Mz=st.Mz + sign * f_el * ef[5],
                    defl_y=st.defl_y + sign * f_el * ed[0],
                    defl_z=st.defl_z + sign * f_el * ed[1]))
            cr.members[mid] = MemberResult(member=mid, length=mr_g.length,
                                           stations=stations)
        for nid, rg in case_grav.reactions.items():
            re = E["reaction"].get(nid, (0,) * 6)
            cr.reactions[nid] = tuple(rg[c] + sign * f_el * re[c]
                                      for c in range(6))
        for nid, dg in case_grav.displacements.items():
            de = E["displacement"].get(nid, (0,) * 6)
            cr.displacements[nid] = tuple(dg[c] + sign * f_el * de[c]
                                          for c in range(6))
        _storey_results(cr, model, E, s)
        out.append(cr)
    return out


def _interp(xs, vals, x):
    """Linear-interpolate the per-component envelope (vals aligned to xs) at x."""
    if not xs or not vals:
        return tuple([0.0] * len(vals[0])) if vals else (0.0, 0.0)
    if x <= xs[0]:
        return tuple(vals[0])
    if x >= xs[-1]:
        return tuple(vals[-1])
    for a in range(len(xs) - 1):
        if xs[a] <= x <= xs[a + 1]:
            span = xs[a + 1] - xs[a]
            t = (x - xs[a]) / span if span > 1e-12 else 0.0
            return tuple(vals[a][c] + (vals[a + 1][c] - vals[a][c]) * t
                         for c in range(len(vals[a])))
    return tuple(vals[-1])


def beam_storey_levels(model: RackModel) -> List[float]:
    """Storey elevations for drift: base + each pallet-beam floor level."""
    z_min = min(n.z for n in model.nodes.values())
    floors = set()
    for m in model.members.values():
        if m.member_set == "pallet beams":
            floors.add(round(model.nodes[m.node_i].z, 3))
    return [z_min] + sorted(z for z in floors if z > z_min + 1e-6)


def _storey_results(cr: CaseResult, model: RackModel, E, s) -> None:
    """Inter-storey drift evaluated PER UPRIGHT COLUMN: for each upright line
    (same x, y) the relative horizontal displacement between the node at the
    upper level and the node at the lower level; the storey drift is the worst
    column. (IS 1893 Cl 7.11.1 - checked at each node/level.)"""
    levels = beam_storey_levels(model)
    # columns keyed by (x, y); only real uprights (exclude the spine line)
    cols: Dict[Tuple[int, int], Dict[int, int]] = {}
    for nid_, n in model.nodes.items():
        if (nid_ // 10000) % 10 == 8:        # spine line index _SP = 8
            continue
        cols.setdefault((round(n.x), round(n.y)), {})[round(n.z)] = nid_

    def disp(nid_: int) -> Tuple[float, float]:
        d = cr.displacements.get(nid_, (0.0, 0.0))
        return d[0], d[1]

    for lo, hi in zip(levels, levels[1:]):
        worst = 0.0
        klo, khi = round(lo), round(hi)
        for zmap in cols.values():
            if klo in zmap and khi in zmap:
                ux0, uy0 = disp(zmap[klo])
                ux1, uy1 = disp(zmap[khi])
                worst = max(worst, math.hypot(ux1 - ux0, uy1 - uy0))
        cr.seismic_storey_drift[hi] = worst


# ------------------------------------------------------------------ orchestrator
def run_seismic(model: RackModel, progress=None) -> List[CaseResult]:
    """Run the full IS 1893 modal RSA and return the SEISMIC design cases.

    ``progress(stage, frac)`` (frac absolute 0..1) is called for each phase so
    the UI can show a live status / progress bar for the seismic run."""
    from .engine.opensees import OpenSeesEngine

    def step(stage, frac):
        if progress:
            progress(stage, frac)

    s = model.seismic
    if not s or not s.enabled:
        return []
    engine = OpenSeesEngine()
    weights = _node_weights(model, s)
    masses = {nid: w / G_MM for nid, w in weights.items()}
    total_W = sum(weights.values())
    if total_W <= 0.0:
        return []

    # ---- modal analysis (Cl 7.7.5.2): request enough modes for >=90% mass in
    # a single build; eigen returns the lowest modes and the per-mode static
    # recovery is cheap, so we ask for max_modes once rather than rebuilding.
    step("Seismic: modal (eigenvalue) analysis", 0.45)
    n = max(s.n_modes, min(s.max_modes, len(model.nodes) * 3 - 1))
    modal = engine.modal(model, masses, n)

    envs: Dict[str, SeismicEnvelope] = {}
    method = "RSA"
    # factored strength rows + the unfactored 1.0(DL+EL) row used ONLY for the
    # drift / P-Delta limit checks (IS 1893 Cl 7.11.1, partial load factor 1.0)
    service_row = ("1.0(DL+EL)", 1.0, s.imposed_factor, 1.0)
    all_rows = list(s.combos) + [service_row]
    grav_jobs = [{"loads": assemble(model, _gravity_combo(r[1], r[2], model)),
                  "name": f"_grav{r[0]}", "combo": r[0], "kind": "SEISMIC",
                  "_grav": True} for r in all_rows]
    if modal and modal.converged and modal.periods:
        nmodes = len(modal.periods)
        step(f"Seismic: response spectrum, {nmodes} modes — recovering forces "
             "(single build, all modes + combinations)", 0.52)
        # ONE build for every per-mode recovery AND every gravity row
        mode_jobs = []
        for comp, d in ((0, "X"), (1, "Y")):
            for k, Tk in enumerate(modal.periods):
                Ah = horizontal_seismic_coefficient(Tk, s)
                mode_jobs.append({"loads": modal_force_loads(
                    model, weights, modal.shapes, k, comp, Ah),
                    "name": f"_m{k}{d}", "combo": "seismic",
                    "kind": "SEISMIC", "_d": d})
        allres = engine.run_static_batch(model, mode_jobs + grav_jobs)
        recovered = allres[:len(mode_jobs)]
        grav_results = allres[len(mode_jobs):]
        step("Seismic: SRSS modal combination + base-shear scaling", 0.62)
        for comp, d in ((0, "X"), (1, "Y")):
            per_mode = [r for r, j in zip(recovered, mode_jobs)
                        if j["_d"] == d]
            env = srss_envelope(per_mode, modal.periods, d, s)
            _scale_to_static(env, model, weights, modal.shapes, modal.periods,
                             s, comp, total_W)
            _apply_pallet_sliding(env, model, s, total_W)
            envs[d] = env
    else:
        method = "ELF"
        step("Seismic: equivalent static (ELF) fallback", 0.55)
        for comp, d in ((0, "X"), (1, "Y")):
            envs[d] = _elf_envelope(engine, model, weights, total_W, s, comp, d)
            _apply_pallet_sliding(envs[d], model, s, total_W)
        grav_results = engine.run_static_batch(model, grav_jobs)

    step("Seismic: directional (100%+30%) + design combinations", 0.66)
    E = _directional(envs["X"], envs["Y"])

    cases: List[CaseResult] = []
    for row, grav in zip(all_rows, grav_results):
        if grav.converged:
            cases += superpose_seismic_cases(grav, E, model, row, s,
                                             service=(row is service_row))

    model.seismic_summary = _summary(model, s, modal, envs, method, total_W)
    step("Seismic: complete", 0.72)
    return cases


def _captured(weights, shapes, comp, total_W) -> float:
    if total_W <= 0:
        return 0.0
    tot = sum(_participation(weights, shapes, k, comp)[1]
              for k in range(len(next(iter(shapes.values())))))
    return tot / total_W


def _gravity_combo(f_d: float, f_il: float, model: RackModel) -> Combination:
    factors = {}
    if "dead" in model.load_cases:
        factors["dead"] = f_d
    if "pallets" in model.load_cases and f_il:
        factors["pallets"] = f_il
    return Combination("seismic-gravity", "SEISMIC", factors,
                       imperfection=False)


def _elf_envelope(engine, model, weights, total_W, s, comp, d
                  ) -> SeismicEnvelope:
    """Equivalent lateral force fallback (Cl 7.6/7.7.1)."""
    Ah = horizontal_seismic_coefficient(empirical_period(model, d), s)
    Vb = Ah * total_W
    z_min = min(n.z for n in model.nodes.values())
    denom = sum(w * (model.nodes[nid].z - z_min) ** 2
                for nid, w in weights.items()) or 1.0
    loads = AssembledLoads()
    for nid, w in weights.items():
        qi = Vb * w * (model.nodes[nid].z - z_min) ** 2 / denom
        loads.add_nodal(nid, qi if comp == 0 else 0.0,
                        0.0 if comp == 0 else qi, 0.0, 0.0, 0.0, 0.0)
    case = engine.run_case(model, loads, name=f"_elf{d}", combo="seismic",
                           kind="SEISMIC", order=1)
    env = srss_envelope([case], [empirical_period(model, d)], d, s)
    env.base_shear, env.method = Vb, "ELF"
    return env


def _summary(model, s, modal, envs, method, total_W) -> dict:
    Z = ZONE_FACTORS.get(s.zone, 0.16)
    modes = []
    if modal and modal.converged:
        weights = _node_weights(model, s)
        for k, Tk in enumerate(modal.periods):
            mx = _participation(weights, modal.shapes, k, 0)[1] / total_W
            my = _participation(weights, modal.shapes, k, 1)[1] / total_W
            modes.append({"mode": k + 1, "T": round(Tk, 3),
                          "mass_x_pct": round(100 * mx, 1),
                          "mass_y_pct": round(100 * my, 1)})
    return {
        "method": method, "zone": s.zone, "Z": Z,
        "structure_type": getattr(s, "structure_type", "-"),
        "damping_pct": round(100 * s.damping, 1),
        "imposed_factor": s.imposed_factor,
        "ed2": round(max(0.55, min(1.0, getattr(s, "ed2", 1.0) or 1.0)), 3),
        "soil": s.soil_type, "I": s.importance, "R": s.response_reduction,
        "seismic_weight_kN": round(total_W / 1e3, 1),
        "Ah_design": round(horizontal_seismic_coefficient(
            empirical_period(model, "X"), s), 4),
        "base_shear_x_kN": round(envs.get("X", SeismicEnvelope("X")).base_shear
                                 / 1e3, 1),
        "base_shear_y_kN": round(envs.get("Y", SeismicEnvelope("Y")).base_shear
                                 / 1e3, 1),
        "fundamental_T": modes[0]["T"] if modes else None,
        "modes": modes,
        "captured_mass_x_pct": round(100 * _captured(
            _node_weights(model, s), modal.shapes, 0, total_W), 1)
        if modal and modal.converged else None,
        # empirical-period / base-shear basis (Cl 7.6 / 7.7.3); the empirical
        # period uses the full rack height (base plate to top of uprights)
        "height_m": round(model.height() / 1000.0, 2),
        "T_emp_x": round(empirical_period(model, "X"), 3),
        "T_emp_y": round(empirical_period(model, "Y"), 3),
        "scaling_on": bool(s.apply_base_shear_scaling),
        "sa_g_modal": (round(design_spectrum_sa_g(modes[0]["T"], s.soil_type), 2)
                       if modes else None),
        "sa_g_emp_x": round(design_spectrum_sa_g(
            empirical_period(model, "X"), s.soil_type), 2),
        "v_dyn_x_kN": round(envs.get("X", SeismicEnvelope("X")).v_dyn / 1e3, 1),
        "v_static_x_kN": round(
            envs.get("X", SeismicEnvelope("X")).v_static / 1e3, 1),
        "scale_x": round(envs.get("X", SeismicEnvelope("X")).scale, 2),
        "scale_y": round(envs.get("Y", SeismicEnvelope("Y")).scale, 2),
        "pallet_sliding": bool(getattr(s, "pallet_sliding", False)),
        "pallet_mu": getattr(s, "pallet_mu", None),
        "sliding_scale_x": round(
            getattr(envs.get("X", SeismicEnvelope("X")), "sliding_scale", 1.0), 2),
    }
