"""Parametric generator for multi-deep racking — drive-in, drive-through and
radio-shuttle (LIFO / FIFO).  Dispatched from builder.build_rack when
RackConfig.system_type != "selective".

The geometry reproduces the client RSTAB model (decoded from the export):

  axes: X = width / down-aisle (lanes side by side), Y = depth / into the lane,
        Z = up.

  * FRAMES at width lines X = k*lane_width (k = 0..n_lanes); each frame is a
    depth ladder of uprights at Y = d*deep_pitch (d = 0..n_deep), continuous
    over the height, braced in its own depth-vertical (Y-Z) plane (D or X);
  * CANTILEVER ARMS: short X members from each upright out to the rail line,
    length arm_length, into each adjacent lane and at every rail level;
  * RAILS run in the depth on the arm tips (offset arm_length into the lane),
    one per lane side per level — pallets bridge a lane on its two rails; the
    arm offset gives the pallet-to-rail eccentricity automatically;
  * TOP BEAMS (X) tie all frame tops across the width;
  * REAR SPINE: X-Z cross-bracing in the closed-end depth plane across the
    lanes (drive-in / LIFO; absent for drive-through / FIFO), with down-aisle
    beams at each level between the braced bays;
  * PLAN BRACING (X-Y) at the top;
  * pinned bases at every upright; semi-rigid rail/beam connectors.

Load on each rail = lane-level total halved onto the two side rails, spread as
a UDL over the rail length (mirrors the SPR beam rule).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .library import SectionLibrary
from .model import (Combination, Imperfection, LoadCase, MemberLoad, NodalLoad,
                    RackModel, SeismicSettings, Steel, Support)

_TOL = 1.0


def _open_faces(variant: str) -> Tuple[bool, bool]:
    """(front_open, rear_open).  Front (d=n_deep) is always the access face;
    the rear (d=0) is closed for LIFO/drive-in, open for FIFO/drive-through."""
    v = (variant or "drive_in").lower()
    rear_open = v in ("drive_through", "shuttle_fifo")
    return True, rear_open


def build_drive_in(cfg) -> RackModel:
    lib = cfg.master.library if cfg.master else (cfg.library
                                                 or SectionLibrary.bundled())
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)

    def pick(name, role):
        if name and name in lib.sections:
            return lib.get(name)
        from .cf_sections import lipped_channel, parse_1c
        if name:
            dims = parse_1c(name)
            if dims:
                return lipped_channel(name, *dims)
        cands = lib.names(role) or lib.names()
        return lib.get(cands[0])

    up = pick(cfg.upright_section, "upright")
    brace = pick(cfg.brace_section, "bracing")
    arm = pick(cfg.arm_section or cfg.beam_section, "beam")
    rail = pick(cfg.rail_section or cfg.beam_section, "beam")
    top = pick(cfg.portal_section or cfg.top_beam_section or cfg.beam_section,
               "beam")
    spine_sec = pick(cfg.spine_bracing_section or cfg.brace_section, "bracing")
    plan_sec = pick(cfg.plan_bracing_section or cfg.brace_section, "bracing")
    for sec in {s.name: s for s in (up, brace, arm, rail, top, spine_sec,
                                    plan_sec)}.values():
        fy = cfg.master.fy.get(sec.name) if cfg.master else None
        if fy:
            mat = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat, Steel(mat, fy=fy))
            sec.material = mat
        else:
            sec.material = "steel"
        m.sections[sec.name] = sec

    # ---- elevations --------------------------------------------------------
    if cfg.levels:
        rail_levels, z = [], 0.0
        for ls in cfg.levels:
            z += ls.gap
            rail_levels.append(z)
    else:
        rail_levels = sorted(cfg.beam_levels)
    if not rail_levels:
        raise ValueError("define at least one storage level")
    H = cfg.frame_height or (rail_levels[-1] + 1000.0)
    H = max(H, rail_levels[-1] + _TOL)
    zs = sorted({0.0, *rail_levels, H})

    def rz(z):
        return round(z, 3)

    # ---- grid --------------------------------------------------------------
    # depth frames: 2-leg ladders (legs frame_depth apart) repeated with a gap.
    # n_deep = number of pallet gaps => n_deep+1 frames. dy = leg Y positions;
    # frame bays (braced) are within-frame leg pairs, gap bays are unbraced.
    lw = cfg.lane_width
    nL, nD = cfg.n_lanes, cfg.n_deep
    fd = cfg.frame_depth
    gap = cfg.deep_pitch or (cfg.pallet_depth + cfg.deep_clearance)
    pitch = fd + gap
    dy: List[float] = []
    frame_bays: List[int] = []                   # bay index i = (dy[i], dy[i+1])
    for f in range(nD + 1):
        y0 = f * pitch
        frame_bays.append(len(dy))               # the within-frame bay
        dy.append(y0)
        dy.append(y0 + fd)
    nDpos = len(dy)                              # number of depth positions
    front_open, rear_open = _open_faces(cfg.di_variant)
    rail_length = dy[-1]

    node_of: Dict[tuple, int] = {}
    rail_of: Dict[tuple, int] = {}
    ctr = [0]

    def NN(x, y, z):
        ctr[0] += 1
        m.add_node(ctr[0], x, y, z)
        return ctr[0]

    for k in range(nL + 1):
        for di in range(nDpos):
            for z in zs:
                node_of[(k, di, rz(z))] = NN(k * lw, dy[di], z)

    mid = 1
    zz = sorted(zs)

    # ---- uprights (legs of each depth frame, at every width line) ----------
    for k in range(nL + 1):
        for di in range(nDpos):
            for a, b in zip(zz, zz[1:]):
                m.add_member(mid, node_of[(k, di, rz(a))],
                             node_of[(k, di, rz(b))], up.name,
                             member_set="uprights", mesh=cfg.mesh_upright)
                mid += 1

    # ---- frame bracing (within each frame's 2 legs only; gaps stay clear) --
    xpat = (cfg.bracing_type or "D").upper() == "X"
    for k in range(nL + 1):
        for bi in frame_bays:                    # only the within-frame bays
            for i, (a, b) in enumerate(zip(zz, zz[1:])):
                na = node_of[(k, bi, rz(a))]
                nb = node_of[(k, bi + 1, rz(b))]
                nc = node_of[(k, bi + 1, rz(a))]
                ndn = node_of[(k, bi, rz(b))]
                if xpat:
                    m.add_member(mid, na, nb, brace.name, mtype="truss",
                                 member_set="bracing"); mid += 1
                    m.add_member(mid, nc, ndn, brace.name, mtype="truss",
                                 member_set="bracing"); mid += 1
                else:                            # D: alternating zigzag
                    if i % 2 == 0:
                        m.add_member(mid, na, nb, brace.name, mtype="truss",
                                     member_set="bracing")
                    else:
                        m.add_member(mid, nc, ndn, brace.name, mtype="truss",
                                     member_set="bracing")
                    mid += 1

    # ---- cantilever arms + rails (continuous in depth on the arm tips) -----
    a_len = cfg.arm_length or 200.0
    for k in range(nL + 1):
        sides = []
        if k < nL:
            sides.append(+1)
        if k > 0:
            sides.append(-1)
        for side in sides:
            for z in rail_levels:
                for di in range(nDpos):
                    rn = NN(k * lw + side * a_len, dy[di], z)
                    rail_of[(k, side, di, rz(z))] = rn
                    m.add_member(mid, node_of[(k, di, rz(z))], rn, arm.name,
                                 mtype="beam", member_set="rail arms")
                    mid += 1
                for di in range(nDpos - 1):
                    m.add_member(mid, rail_of[(k, side, di, rz(z))],
                                 rail_of[(k, side, di + 1, rz(z))], rail.name,
                                 mtype="beam", member_set="rail beams",
                                 mesh=cfg.mesh_beam)
                    mid += 1

    # ---- top beams (X across frames, every depth line) --------------------
    for di in range(nDpos):
        for k in range(nL):
            m.add_member(mid, node_of[(k, di, rz(H))],
                         node_of[(k + 1, di, rz(H))], top.name,
                         mtype="beam", member_set="portal beams")
            mid += 1

    # ---- rear spine (X-Z cross-bracing at the closed end) + level beams ----
    has_spine = (not rear_open) and cfg.spine_position != "none"
    if has_spine:
        d_s = 0                                  # rear / closed end
        for k in range(nL):
            for a, b in zip(zz, zz[1:]):
                m.add_member(mid, node_of[(k, d_s, rz(a))],
                             node_of[(k + 1, d_s, rz(b))], spine_sec.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1
                m.add_member(mid, node_of[(k + 1, d_s, rz(a))],
                             node_of[(k, d_s, rz(b))], spine_sec.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1
        for z in rail_levels:                    # down-aisle beams at the rear
            for k in range(nL):
                m.add_member(mid, node_of[(k, d_s, rz(z))],
                             node_of[(k + 1, d_s, rz(z))], top.name,
                             mtype="beam", member_set="portal beams")
                mid += 1

    # ---- plan bracing (X-Y at the top) — selective (alternate lanes) -------
    plan_lanes = (range(nL) if cfg.plan_bracing_modules == "all"
                  else range(0, nL, 3) if cfg.plan_bracing_modules == "every_3rd"
                  else range(0, nL, 2))          # default: alternate lanes
    for k in plan_lanes:
        for di in range(nDpos - 1):              # single diagonal per cell
            m.add_member(mid, node_of[(k, di, rz(H))],
                         node_of[(k + 1, di + 1, rz(H))], plan_sec.name,
                         mtype="truss", member_set="plan bracing"); mid += 1

    # ---- supports (pinned bases) ------------------------------------------
    for k in range(nL + 1):
        for di in range(nDpos):
            m.supports.append(Support(node_of[(k, di, rz(0.0))], ux=True,
                                      uy=True, uz=True, rx=False, ry=False,
                                      rz=False))

    _loads(m, cfg, rail_levels, rail_length, node_of, rz, nDpos, nL)
    _checks(m, cfg, nL)
    return m


def _loads(m, cfg, rail_levels, rail_length, node_of, rz, nDpos, nL) -> None:
    Q = cfg.n_deep * cfg.weight_per_pallet       # lane-level total
    w_rail = (Q / 2.0) / rail_length if rail_length > 0 else 0.0
    dead = LoadCase("dead", "permanent")
    pallets = LoadCase("pallets", "variable")
    for mm in m.members.values():
        if mm.member_set in ("rail beams", "rail arms"):
            dead.member_loads.append(MemberLoad(mm.id, qz=-cfg.dead_load_beam))
        if mm.member_set == "rail beams":
            pallets.member_loads.append(MemberLoad(mm.id, qz=-w_rail))
    m.load_cases["dead"] = dead
    m.load_cases["pallets"] = pallets

    top_front = node_of[(0, nDpos - 1, rz(rail_levels[-1]))]
    place = LoadCase("placement", "variable")
    place.nodal_loads.append(NodalLoad(top_front, fx=cfg.placement_load))
    m.load_cases["placement"] = place
    place_y = LoadCase("placement_y", "variable")
    place_y.nodal_loads.append(NodalLoad(top_front, fy=cfg.placement_load))
    m.load_cases["placement_y"] = place_y

    impact = cfg.impact_load and cfg.impact_height > 0
    if impact:
        zj = min(rail_levels, key=lambda z: abs(z - cfg.impact_height))
        n_imp = node_of[(0, nDpos - 1, rz(zj))]
        ix = LoadCase("impact_x", "accidental")
        ix.nodal_loads.append(NodalLoad(n_imp, fx=cfg.impact_load))
        m.load_cases["impact_x"] = ix
        iy = LoadCase("impact_y", "accidental")
        iy.nodal_loads.append(NodalLoad(n_imp, fy=2.0 * cfg.impact_load))
        m.load_cases["impact_y"] = iy

    m.combinations = [
        Combination("ULS1", "ULS", {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q}),
        Combination("ULS2", "ULS", {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                                    "placement": cfg.gamma_Q}),
        Combination("ULS3", "ULS", {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                                    "placement_y": cfg.gamma_Q}),
        Combination("SLS1", "SLS", {"dead": 1.0, "pallets": 1.0},
                    imperfection=False),
    ]
    if impact:
        m.combinations.insert(3, Combination(
            "ULS-impactX", "ULS",
            {"dead": 1.0, "pallets": 1.0, "impact_x": 1.0}, imp_directions=["+x"]))
        m.combinations.insert(4, Combination(
            "ULS-impactY", "ULS",
            {"dead": 1.0, "pallets": 1.0, "impact_y": 1.0}, imp_directions=["+y"]))
    m.imperfection = Imperfection(
        n_cols=nL + 1, phi_s=cfg.phi_s, phi_l=cfg.connector_looseness,
        method="EHF", directions=["+x", "-x", "+y", "-y"])


def _checks(m, cfg, nL) -> None:
    m.checks.buckling_sets = ["uprights"]
    m.checks.bolt_d = cfg.bolt_d
    m.checks.bolt_grade = cfg.bolt_grade
    m.checks.bolts_per_connection = cfg.bolts_per_connection
    m.checks.brace_planes = cfg.brace_planes
    m.checks.beam_laterally_restrained = cfg.beam_laterally_restrained
    if cfg.seismic:
        m.seismic = SeismicSettings(
            enabled=True, zone=cfg.seismic_zone, soil_type=cfg.seismic_soil,
            importance=cfg.seismic_importance,
            response_reduction=cfg.seismic_response_reduction,
            damping=cfg.seismic_damping,
            imposed_factor=cfg.seismic_imposed_factor,
            n_modes=cfg.seismic_n_modes)
