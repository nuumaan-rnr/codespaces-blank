"""Parametric generator for multi-deep racking: drive-in, drive-through and
radio-shuttle (LIFO / FIFO).  Dispatched from builder.build_rack when
RackConfig.system_type != "selective".

Geometry (axes: X = width / down-aisle, Y = depth / into the lane, Z = up):
  * width lines k = 0..n_lanes at x = k*lane_width (n_lanes lanes between them);
  * depth positions d = 0..n_deep at y = d*p, p = pallet_depth + deep_clearance;
  * uprights at every (k, d) node — these are the depth "frames" (one per width
    line), braced in their own depth-vertical (Y-Z) plane at the lane sides so
    the lanes stay clear for the truck/shuttle;
  * depth-running rails (Y) at each width line per level carry the pallets;
  * radio-shuttle adds down-aisle (X) load beams at every level with the rails
    on top; drive-in uses cantilever rails on the uprights;
  * top-tie / portal beams (X) across the frame tops, a top plan-bracing plane
    (X-Y), and a vertical spine (X-Z) at the rear (LIFO / drive-in) or centre
    (FIFO option) — none when open both ends.

The load on each rail is the lane-level total halved onto the two side rails and
spread as a UDL over the rail length (mirrors the SPR beam rule).  First cut:
geometry + gravity (ULS/SLS) + the existing EN 15512 checks, plus the FEM
10.2.07 placement (0.5 kN) and forklift-impact load cases.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .library import SectionLibrary
from .model import (Combination, Hinge, Imperfection, LoadCase, MemberLoad,
                    NodalLoad, RackModel, SeismicSettings, Steel, Support)

_TOL = 1.0


def _nid(k: int, d: int, j: int) -> int:
    """Node id: width line k, depth position d, elevation index j."""
    return k * 1_000_000 + d * 1_000 + j


def _open_faces(variant: str) -> Tuple[bool, bool]:
    """(front_open, rear_open) by variant."""
    v = (variant or "drive_in").lower()
    if v in ("drive_through", "shuttle_fifo"):
        return True, True          # FIFO: both ends open
    return True, False             # LIFO / drive-in: front open, rear closed


def _is_shuttle(variant: str) -> bool:
    return "shuttle" in (variant or "").lower()


def build_drive_in(cfg) -> RackModel:
    lib = cfg.master.library if cfg.master else (cfg.library
                                                 or SectionLibrary.bundled())
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)

    # ---- section resolution (reuse the SPR helpers' fallbacks) --------------
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
    end_up = pick(cfg.end_frame_section or cfg.upright_section, "upright")
    rail = pick(cfg.rail_section or cfg.beam_section, "beam")
    levbeam = pick(cfg.level_beam_section or cfg.beam_section, "beam")
    portal = pick(cfg.portal_section or cfg.beam_section, "beam")
    topbeam = pick(cfg.top_beam_section or cfg.beam_section, "beam")
    brace = pick(cfg.brace_section, "bracing")
    plan = pick(cfg.plan_bracing_section or cfg.brace_section, "bracing")
    spine = pick(cfg.spine_bracing_section or cfg.brace_section, "bracing")
    for sec in {s.name: s for s in (up, end_up, rail, levbeam, portal, topbeam,
                                    brace, plan, spine)}.values():
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
    top_load = rail_levels[-1]
    H = cfg.frame_height or (top_load + cfg.internal_frame_extra)
    H = max(H, top_load + _TOL)
    H_int = top_load + cfg.internal_frame_extra        # truncated internal frame

    zs = sorted({0.0, *rail_levels, H, H_int})
    j_of = {round(z, 3): j for j, z in enumerate(zs)}

    def jz(z):
        return j_of[round(z, 3)]

    # ---- grid --------------------------------------------------------------
    p = cfg.pallet_depth + cfg.deep_clearance
    n_w = cfg.n_lanes + 1                  # width lines
    n_d = cfg.n_deep + 1                   # depth positions (frames)
    rail_len = cfg.n_deep * p
    front_open, rear_open = _open_faces(cfg.di_variant)
    shuttle = _is_shuttle(cfg.di_variant)
    # which width-line frames are full height vs truncated:
    end_w = {0, cfg.n_lanes}              # outer width lines: reinforced
    # v1: all frames full height so the top plan bracing connects; the
    # internal-frame truncation option is applied in a later pass.
    def frame_top(k):
        return H

    for k in range(n_w):
        ftop = frame_top(k)
        for d in range(n_d):
            for z in zs:
                if z <= ftop + _TOL:
                    m.add_node(_nid(k, d, jz(z)), k * cfg.lane_width,
                               d * p, z)

    mid = 1
    # ---- uprights (depth frames at each width line) ------------------------
    for k in range(n_w):
        ftop = frame_top(k)
        sec = end_up.name if (k in end_w and cfg.end_frame_3upright) else up.name
        ks = [z for z in zs if z <= ftop + _TOL]
        for d in range(n_d):
            for a, b in zip(ks, ks[1:]):
                m.add_member(mid, _nid(k, d, jz(a)), _nid(k, d, jz(b)), sec,
                             member_set="uprights", mesh=cfg.mesh_upright)
                mid += 1

    # ---- frame bracing (in-plane, depth-vertical Y-Z, at each width line) ---
    # diagonals along the depth bays, full height or top band only
    for k in range(n_w):
        ftop = frame_top(k)
        ks = [z for z in zs if z <= ftop + _TOL]
        lo = 0 if cfg.frame_brace_extent == "full" else max(0, len(ks) - 2)
        for d in range(cfg.n_deep):
            for a, b in zip(ks[lo:], ks[lo + 1:]):
                m.add_member(mid, _nid(k, d, jz(a)), _nid(k, d + 1, jz(b)),
                             brace.name, mtype="truss", member_set="bracing")
                mid += 1

    # ---- rails (depth-running Y) per width line per level ------------------
    # at open faces, the first/last bay is a cantilever connector (no rail
    # segment spanning the face)
    for k in range(n_w):
        for z in rail_levels:
            for d in range(cfg.n_deep):
                if front_open and d == 0:
                    continue           # cantilever at the open front face
                if rear_open and d == cfg.n_deep - 1:
                    continue           # cantilever at the open rear face
                m.add_member(mid, _nid(k, d, jz(z)), _nid(k, d + 1, jz(z)),
                             rail.name, mtype="beam", member_set="rail beams",
                             mesh=cfg.mesh_beam)
                mid += 1

    # ---- radio-shuttle: down-aisle (X) level beams carrying the rails ------
    if shuttle:
        for z in rail_levels:
            for d in range(n_d):
                for k in range(cfg.n_lanes):
                    m.add_member(mid, _nid(k, d, jz(z)), _nid(k + 1, d, jz(z)),
                                 levbeam.name, mtype="beam",
                                 member_set="level beams", mesh=cfg.mesh_beam)
                    mid += 1

    # ---- portal / top-tie beams (X) across frame tops ----------------------
    for d in range(n_d):
        for k in range(cfg.n_lanes):
            za = min(frame_top(k), frame_top(k + 1))
            m.add_member(mid, _nid(k, d, jz(za)), _nid(k + 1, d, jz(za)),
                         portal.name, mtype="beam", member_set="portal beams")
            mid += 1

    # ---- tall-frame stability beam at the access face(s) -------------------
    # frame height > threshold: a beam across the access-face uprights just
    # below the 2nd (or 3rd, taller) level stiffens the entry frame. LIFO =
    # front only; FIFO = front + rear.
    if H > cfg.tall_frame_threshold and len(rail_levels) >= 2:
        z_stab = rail_levels[2] if (len(rail_levels) >= 3
                                    and H > 1.5 * cfg.tall_frame_threshold) \
            else rail_levels[1]
        faces = [0] + ([cfg.n_deep] if rear_open else [])
        for d in faces:
            for k in range(cfg.n_lanes):
                m.add_member(mid, _nid(k, d, jz(z_stab)),
                             _nid(k + 1, d, jz(z_stab)), topbeam.name,
                             mtype="beam", member_set="portal beams")
                mid += 1

    # ---- top plan bracing (X-Y horizontal) ---------------------------------
    plan_levels = list(rail_levels) if (shuttle and cfg.plan_every_level) \
        else [H]
    for z in plan_levels:
        for k in range(cfg.n_lanes):
            for d in range(cfg.n_deep):
                if frame_top(k) + _TOL < z or frame_top(k + 1) + _TOL < z:
                    continue
                m.add_member(mid, _nid(k, d, jz(z)), _nid(k + 1, d + 1, jz(z)),
                             plan.name, mtype="truss", member_set="plan bracing")
                mid += 1
                m.add_member(mid, _nid(k + 1, d, jz(z)), _nid(k, d + 1, jz(z)),
                             plan.name, mtype="truss", member_set="plan bracing")
                mid += 1

    # ---- spine bracing (vertical X-Z braced bay) ---------------------------
    # "auto": rear when the rear face is closed (drive-in / LIFO); none when
    # both ends are accessible, i.e. drive-through / FIFO.
    pos = cfg.spine_position
    if pos == "auto":
        pos = "none" if rear_open else "rear"
    if pos == "rear":
        d_spine = cfg.n_deep
    elif pos == "centre":
        d_spine = cfg.n_deep // 2
    else:
        d_spine = None
    if d_spine is not None:
        for k in range(cfg.n_lanes):
            ftop = min(frame_top(k), frame_top(k + 1))
            ks = [z for z in zs if z <= ftop + _TOL]
            for a, b in zip(ks, ks[1:]):
                m.add_member(mid, _nid(k, d_spine, jz(a)),
                             _nid(k + 1, d_spine, jz(b)), spine.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1
                m.add_member(mid, _nid(k + 1, d_spine, jz(a)),
                             _nid(k, d_spine, jz(b)), spine.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1

    # ---- top depth-tie (drive-in option): Y member along frame tops --------
    if cfg.top_depth_tie:
        for k in range(n_w):
            ftop = frame_top(k)
            for d in range(cfg.n_deep):
                m.add_member(mid, _nid(k, d, jz(ftop)), _nid(k, d + 1, jz(ftop)),
                             portal.name, mtype="beam", member_set="portal beams")
                mid += 1

    # ---- supports (base springs at every upright) --------------------------
    k_base = float(cfg.base_stiffness) if cfg.base_stiffness != "auto" else 5.0e8
    for k in range(n_w):
        for d in range(n_d):
            m.supports.append(Support(_nid(k, d, 0), ux=True, uy=True, uz=True,
                                      rx=k_base or False, ry=k_base or False,
                                      rz=False))

    _drive_in_loads(m, cfg, rail_levels, rail_len, n_w, jz, front_open,
                    rear_open)
    _drive_in_checks(m, cfg, n_w)
    return m


def _drive_in_loads(m, cfg, rail_levels, rail_len, n_w, jz, front_open,
                    rear_open) -> None:
    # pallet load: lane total Q = n_deep*weight_per_pallet, halved to the two
    # side rails, UDL over the rail length (load/mm).  An interior rail (width
    # line 1..n_lanes-1) carries half from each adjacent lane = a full lane's
    # worth; the two outer rails carry half a lane.
    Q = cfg.n_deep * cfg.weight_per_pallet
    w_half = (Q / 2.0) / rail_len if rail_len > 0 else 0.0

    def rail_ids_at(k):
        return [mm.id for mm in m.members.values()
                if mm.member_set == "rail beams"
                and mm.node_i // 1_000_000 == k]

    dead = LoadCase("dead", "permanent")
    pallets = LoadCase("pallets", "variable")
    for mm in m.members.values():
        if mm.member_set in ("rail beams", "level beams"):
            dead.member_loads.append(MemberLoad(mm.id, qz=-cfg.dead_load_beam))
    for k in range(n_w):
        outer = (k == 0 or k == cfg.n_lanes)
        w = w_half if outer else 2.0 * w_half      # interior rail: two lanes
        for rid in rail_ids_at(k):
            pallets.member_loads.append(MemberLoad(rid, qz=-w))
    m.load_cases["dead"] = dead
    m.load_cases["pallets"] = pallets

    # pallet-to-rail eccentricity (FEM 10.2.07): the pallet bears on the rail
    # top offset from the upright centroid → an eccentric moment on the upright
    # at each rail-bearing node (= tributary vertical load × eccentricity).
    if cfg.rail_eccentricity:
        from collections import defaultdict
        mom: Dict[int, float] = defaultdict(float)
        for ml in pallets.member_loads:
            mm = m.members[ml.member]
            if mm.member_set != "rail beams":
                continue
            half = abs(ml.qz) * m.member_length(mm) / 2.0
            mom[mm.node_i] += half * cfg.rail_eccentricity
            mom[mm.node_j] += half * cfg.rail_eccentricity
        for nid, mx in mom.items():
            pallets.nodal_loads.append(NodalLoad(nid, mx=mx))

    # placement load (FEM 10.2.07: 0.5 kN both directions at top rail level)
    top_j = jz(rail_levels[-1])
    place = LoadCase("placement", "variable")
    place.nodal_loads.append(NodalLoad(_nid(0, 0, top_j), fx=cfg.placement_load))
    m.load_cases["placement"] = place
    place_y = LoadCase("placement_y", "variable")
    place_y.nodal_loads.append(NodalLoad(_nid(0, 0, top_j),
                                         fy=cfg.placement_load))
    m.load_cases["placement_y"] = place_y

    # forklift impact (accidental) on the front/entry upright
    impact = cfg.impact_load and cfg.impact_height > 0
    if impact:
        # apply at the node nearest the impact height on the front upright
        j_imp = _nearest_level_j(m, 0, 0, cfg.impact_height)
        ix = LoadCase("impact_x", "accidental")
        ix.nodal_loads.append(NodalLoad(_nid(0, 0, j_imp), fx=cfg.impact_load))
        m.load_cases["impact_x"] = ix
        iy = LoadCase("impact_y", "accidental")
        iy.nodal_loads.append(NodalLoad(_nid(0, 0, j_imp), fy=cfg.impact_load))
        m.load_cases["impact_y"] = iy

    # combinations (reuse the SPR set)
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
        n_cols=n_w, phi_s=cfg.phi_s, phi_l=cfg.connector_looseness,
        method="EHF", directions=["+x", "-x", "+y", "-y"])


def _nearest_level_j(m, k, d, z):
    """Elevation index of the node nearest to z on the (k, d) upright."""
    best, bj = None, 0
    for nid, n in m.nodes.items():
        if nid // 1_000_000 == k and (nid // 1_000) % 1_000 == d:
            dz = abs(n.z - z)
            if best is None or dz < best:
                best, bj = dz, nid % 1_000
    return bj


def _drive_in_checks(m, cfg, n_w) -> None:
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
