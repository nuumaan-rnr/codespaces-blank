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
  * semi-rigid down-aisle floor connections (from the master's tested base
    table, else calculated from the R899 formulas); semi-rigid rail/beam
    connectors.

Load on each rail = lane-level total halved onto the two side rails, spread as
a UDL over the rail length (mirrors the SPR beam rule).
"""

from __future__ import annotations

from typing import Dict, List, Tuple

from .library import SectionLibrary
from .model import (BuiltUpColumn, Combination, CrossSection, Hinge,
                    Imperfection, LoadCase, MemberLoad, NodalLoad, RackModel,
                    SeismicSettings, Steel, Support)

_TOL = 1.0


def _rstab_arm() -> CrossSection:
    """Cantilever-arm section from the client RSTAB model (cs3
    'UU 30/30/3/3/3/190', 'Arm -200'); inertias cm^4 -> mm^4, area cm^2 -> mm^2."""
    return CrossSection(
        name="UU30x190x3 arm", material="steel",
        A=732.0, Iy=3.1311e6, Iz=38650.0, J=2179.0,
        Wely=3.1311e6 / 95.0, Welz=38650.0 / 15.0,
        role="beam", width_b=30.0, depth_h=190.0, t=3.0,
        # shear areas (RSTAB cs3): Avz is the web (depth) shear for strong-axis
        # bending; Avy the weak-axis (flange) shear.  It_gross = J for FT.
        Avy=53.0, Avz=521.0, It_gross=2179.0,
        description="RSTAB cs3 cantilever arm")


def _rstab_rail() -> CrossSection:
    """Depth rail section from the client RSTAB model (cs4
    'DRIVE-IN RAIL 2.5 MM'); inertias cm^4 -> mm^4, area cm^2 -> mm^2."""
    return CrossSection(
        name="DRIVE-IN RAIL 2.5", material="steel",
        A=709.8, Iy=1.8056e6, Iz=457718.0, J=1462.0,
        Wely=1.8056e6 / 79.68, Welz=457718.0 / 64.22,
        role="beam", width_b=128.44, depth_h=159.37, t=2.5,
        # shear areas (RSTAB cs4): Avz web (depth) shear for strong-axis
        # bending, Avy weak-axis shear.  It_gross = J for FT.
        Avy=265.0, Avz=229.0, It_gross=1462.0,
        description="RSTAB cs4 drive-in rail")


def _select_bays(n: int, modules: str, bay_list) -> List[int]:
    """Width bays (lanes) to brace: an explicit bay list overrides the mode;
    otherwise all / every_3rd / alternate (default)."""
    if bay_list:
        return [k for k in bay_list if 0 <= k < n]
    if modules == "all":
        return list(range(n))
    if modules == "every_3rd":
        return list(range(0, n, 3))
    return list(range(0, n, 2))               # alternate


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
    # cantilever arm + depth rail default to the RSTAB drive-in profiles unless a
    # specific section is named (so the deflection / forces use real properties)
    arm = pick(cfg.arm_section, "beam") if cfg.arm_section else _rstab_arm()
    rail = pick(cfg.rail_section, "beam") if cfg.rail_section else _rstab_rail()
    top = pick(cfg.portal_section or cfg.top_beam_section or cfg.beam_section,
               "beam")
    # rear (back) down-aisle beams: a separate section so the top beams and the
    # back beams can differ (falls back to the top-beam section)
    back = pick(cfg.back_beam_section or cfg.level_beam_section
                or cfg.portal_section or cfg.top_beam_section or cfg.beam_section,
                "beam")
    spine_sec = pick(cfg.spine_bracing_section or cfg.brace_section, "bracing")
    plan_sec = pick(cfg.plan_bracing_section or cfg.brace_section, "bracing")
    for sec in {s.name: s for s in (up, brace, arm, rail, top, back, spine_sec,
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
    from .builder import bracing_elevations
    brace_zs = [z for z in bracing_elevations(cfg, H) if z <= H + _TOL]
    # accidental (forklift) impact height: a node ~400 mm above the base so the
    # impact is applied where a truck actually strikes, not at a rail level
    # (mirrors the SPR rule, builder.py:395).
    acc_h = cfg.accidental_height
    if not (100.0 <= acc_h < H):
        acc_h = min(400.0, 0.5 * H)
    zs = sorted({0.0, *rail_levels, *brace_zs, acc_h, H})

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
    # boxed/built-up end columns (opt-in): tag the two end frames so the
    # EN 1993-1-1 §6.4 BUILT_UP check governs them instead of the single-section
    # STRESS/BUCKLING checks.
    end_k = {0, nL} if getattr(cfg, "built_up_end_columns", False) else set()
    # EN 15512 buckling lengths: cross-aisle (local y) is braced by the frame
    # ladder at the bracing pitch.  Down-aisle (local z) is the full frame height
    # (K = 1.0, pinned-pinned) - the conservative worst case; the engine already
    # runs the second-order sway, and 1.0H gives the highest upright buckling
    # utilisation.
    lcr_ca = float(cfg.bracing_pitch or 600.0)
    lcr_da = H
    for k in range(nL + 1):
        ms = "end columns" if k in end_k else "uprights"
        for di in range(nDpos):
            for a, b in zip(zz, zz[1:]):
                m.add_member(mid, node_of[(k, di, rz(a))],
                             node_of[(k, di, rz(b))], up.name,
                             member_set=ms, mesh=cfg.mesh_upright,
                             L_buckling_y=lcr_ca, L_buckling_z=lcr_da)
                mid += 1

    # ---- frame bracing — same as the SPR frame (bottom + top horizontal
    # struts and D/X diagonals at bracing_pitch), applied within each frame's
    # two legs; the pallet gaps between frames stay clear.
    xpat = (cfg.bracing_type or "D").upper() == "X"
    for k in range(nL + 1):
        for bi in frame_bays:                    # legs (bi, bi+1) of one frame
            la, lb = bi, bi + 1                   # the two legs in depth
            outer = la if cfg.bracing_first_side != "inner" else lb
            inner = lb if outer == la else la
            if not brace_zs:
                continue
            j0, j1 = rz(brace_zs[0]), rz(brace_zs[-1])
            m.add_member(mid, node_of[(k, la, j0)], node_of[(k, lb, j0)],
                         brace.name, mtype="truss", member_set="bracing")
            mid += 1
            if len(brace_zs) > 1:
                m.add_member(mid, node_of[(k, la, j1)], node_of[(k, lb, j1)],
                             brace.name, mtype="truss", member_set="bracing")
                mid += 1
            for p in range(len(brace_zs) - 1):
                ja, jb = rz(brace_zs[p]), rz(brace_zs[p + 1])
                if xpat:
                    m.add_member(mid, node_of[(k, la, ja)], node_of[(k, lb, jb)],
                                 brace.name, mtype="truss", member_set="bracing")
                    mid += 1
                    m.add_member(mid, node_of[(k, lb, ja)], node_of[(k, la, jb)],
                                 brace.name, mtype="truss", member_set="bracing")
                    mid += 1
                else:                            # D zigzag (first side = outer)
                    lo, hi = (outer, inner) if p % 2 == 0 else (inner, outer)
                    m.add_member(mid, node_of[(k, lo, ja)], node_of[(k, hi, jb)],
                                 brace.name, mtype="truss", member_set="bracing")
                    mid += 1

    # ---- cantilever arms + rails (continuous in depth on the arm tips) -----
    # A lane is the clear bay between two frames; its two side rails come from
    # the +side of frame k and the -side of frame k+1, so a rail's lane index is
    # k for side=+1 and k-1 for side=-1.  rail_members records (mid, lane, z, di)
    # so the load builder can form the full / alternate-lane / top-level subsets
    # and load only the deep (pallet) bays.  The cantilever arm-to-upright
    # bracket is a semi-rigid moment connection (stiffness from the arm section
    # connector data, else the cfg connector value).
    a_len = cfg.arm_length or 200.0
    # cantilever bracket connector (RSTAB Konsole hinge jZ = 1.0e6 N*mm/rad);
    # an explicit arm_connector_stiffness wins, else the arm section connector,
    # else the cfg default
    arm_k = (cfg.arm_connector_stiffness if cfg.arm_connector_stiffness
             else (arm.connector_k or cfg.connector_stiffness))
    arm_mrd = cfg.arm_connector_m_rd or arm.connector_m_rd or cfg.connector_m_rd
    arm_loos = (arm.connector_looseness if arm.connector_looseness is not None
                else cfg.connector_looseness)

    def _arm_hinge():
        return Hinge(rz=arm_k, m_rd_z=arm_mrd, looseness=arm_loos)

    rail_members: List[Tuple[int, int, float, int]] = []
    for k in range(nL + 1):
        sides = []
        if k < nL:
            sides.append(+1)
        if k > 0:
            sides.append(-1)
        for side in sides:
            lane = k if side == +1 else k - 1
            for z in rail_levels:
                for di in range(nDpos):
                    rn = NN(k * lw + side * a_len, dy[di], z)
                    rail_of[(k, side, di, rz(z))] = rn
                    m.add_member(mid, node_of[(k, di, rz(z))], rn, arm.name,
                                 mtype="beam", member_set="rail arms",
                                 hinge_i=_arm_hinge())
                    mid += 1
                for di in range(nDpos - 1):
                    m.add_member(mid, rail_of[(k, side, di, rz(z))],
                                 rail_of[(k, side, di + 1, rz(z))], rail.name,
                                 mtype="beam", member_set="rail beams",
                                 mesh=cfg.mesh_beam)
                    rail_members.append((mid, lane, z, di))
                    mid += 1

    # ---- top beams (X across the frame tops) — semi-rigid down-aisle connectors
    # top beams and rear (back) beams are independent: each takes its connector
    # stiffness / M_Rd / looseness from ITS OWN selected section (master), with
    # an optional explicit stiffness override, falling back to the cfg values.
    def _beam_hinge(sec, override):
        k = override if override else (sec.connector_k or cfg.connector_stiffness)
        mrd = sec.connector_m_rd or cfg.connector_m_rd
        ls = (sec.connector_looseness if sec.connector_looseness is not None
              else cfg.connector_looseness)
        return lambda: Hinge(rz=k, m_rd_z=mrd, looseness=ls)

    _top_hinge = _beam_hinge(top, cfg.top_connector_stiffness)
    _back_hinge = _beam_hinge(back, cfg.back_connector_stiffness)

    for di in range(nDpos):
        for k in range(nL):
            m.add_member(mid, node_of[(k, di, rz(H))],
                         node_of[(k + 1, di, rz(H))], top.name,
                         mtype="beam", member_set="portal beams",
                         hinge_i=_top_hinge(), hinge_j=_top_hinge())
            mid += 1

    # ---- rear spine (X-Z cross-bracing at the closed end) + level beams ----
    # RSTAB arrangement: an X-braced tower only in ALTERNATE width bays, with one
    # X panel per STOREY (between the base, the rail levels and the top) - not in
    # every bay and every fine sub-elevation.
    has_spine = (not rear_open) and cfg.spine_position != "none"
    if has_spine:
        d_s = 0                                  # rear / closed end
        # selectable bays (default alternate = RSTAB); one X panel per storey
        spine_lanes = _select_bays(nL, cfg.spine_bracing_modules,
                                   getattr(cfg, "spine_bracing_module_list",
                                           None))
        spine_levels = sorted({0.0, *rail_levels, H})
        for k in spine_lanes:
            for a, b in zip(spine_levels, spine_levels[1:]):
                ja, jb = rz(a), rz(b)
                m.add_member(mid, node_of[(k, d_s, ja)],
                             node_of[(k + 1, d_s, jb)], spine_sec.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1
                m.add_member(mid, node_of[(k + 1, d_s, ja)],
                             node_of[(k, d_s, jb)], spine_sec.name,
                             mtype="truss", member_set="spine bracing")
                mid += 1
        for z in rail_levels:                    # back beams (rear, per level)
            for k in range(nL):
                m.add_member(mid, node_of[(k, d_s, rz(z))],
                             node_of[(k + 1, d_s, rz(z))], back.name,
                             mtype="beam", member_set="back beams",
                             hinge_i=_back_hinge(), hinge_j=_back_hinge())
                mid += 1

    # ---- plan bracing (X-Y at the top of the frames) ----------------------
    # type: 'D' single diagonal or 'X' crossed per cell; modules: an explicit
    # lane list (plan_bracing_module_list) or all / every_3rd / alternate lanes.
    plan_x = (getattr(cfg, "plan_bracing_type", "D") or "D").upper() == "X"
    plan_lanes = _select_bays(nL, cfg.plan_bracing_modules,
                              getattr(cfg, "plan_bracing_module_list", None))
    for k in plan_lanes:
        for di in range(nDpos - 1):
            m.add_member(mid, node_of[(k, di, rz(H))],
                         node_of[(k + 1, di + 1, rz(H))], plan_sec.name,
                         mtype="truss", member_set="plan bracing"); mid += 1
            if plan_x:                           # second crossed diagonal
                m.add_member(mid, node_of[(k + 1, di, rz(H))],
                             node_of[(k, di + 1, rz(H))], plan_sec.name,
                             mtype="truss", member_set="plan bracing"); mid += 1

    # ---- top depth tie: a BEAM along the depth (Y) at the top of each upright
    # line, running front-to-back through the frames AND the gaps (ties the
    # frame tops together along the lane).
    if getattr(cfg, "top_depth_tie", True):
        for k in range(nL + 1):
            for di in range(nDpos - 1):
                m.add_member(mid, node_of[(k, di, rz(H))],
                             node_of[(k, di + 1, rz(H))], top.name,
                             mtype="beam", member_set="top depth ties")
                mid += 1

    # ---- supports (semi-rigid floor connection) ---------------------------
    # Down-aisle rotational base stiffness (applied to ry; cross-aisle rx is held
    # by the braced depth frames, rz free).  Source order:
    #   1. the master's EN 15512 tested BASE_STIFFNESS table, interpolated at the
    #      estimated factored upright axial load; otherwise
    #   2. CALCULATED from the R899 (Gilbert & Rasmussen 2009) formulas - the
    #      concrete-floor term (Eq 43) in series with the upright term (Eq 46),
    #      which need only upright properties, so a value is always available
    #      (there is no pinned fallback).
    # An explicit numeric base_stiffness overrides both.
    n_up = (nL + 1) * nDpos
    if isinstance(cfg.base_stiffness, str):           # 'auto'
        k_base, source = None, ""
        if cfg.master:
            Q_tot = cfg.n_deep * cfg.weight_per_pallet * nL * len(rail_levels)
            N_est = cfg.gamma_Q * Q_tot / n_up if n_up else 0.0
            try:
                k_base, _ = cfg.master.base_stiffness(up.name, N_est)
                source = "master tested table"
            except Exception:
                k_base = None
        if k_base is None:                            # no tested table -> R899
            from .base_stiffness import derived_base_stiffness
            E_up = m.materials[up.material].E
            h0 = rail_levels[0] if rail_levels else H
            k_base = derived_base_stiffness(up, E_up, h0,
                                            f_ck=getattr(cfg, "concrete_fck", 25.0))
            source = "calculated (R899)"
    else:
        k_base = float(cfg.base_stiffness)
        source = "explicit"
    m.base_stiffness_source = source
    m.base_stiffness_value = float(k_base) if k_base else 0.0
    for k in range(nL + 1):
        for di in range(nDpos):
            kk = k_base if k_base and k_base > 0 else False
            m.supports.append(Support(node_of[(k, di, rz(0.0))], ux=True,
                                      uy=True, uz=True, rx=False, ry=kk,
                                      rz=False))

    _loads(m, cfg, rail_levels, rail_length, node_of, rz, nDpos, nL,
           rail_members, acc_h)
    _checks(m, cfg, nL)
    return m


def _loads(m, cfg, rail_levels, rail_length, node_of, rz, nDpos, nL,
           rail_members, acc_h) -> None:
    """Build the drive-in load cases and combinations to mirror the client
    RSTAB scheme (sheets 2.1 / 2.5):

      cases  dead, pallets (full), pallets_alt1/alt2 (even/odd lanes),
             pallets_pattern (checkerboard lane x level), pallets_top (top
             level only), placement (+X) / placement_y (+Y), impact_x / impact_y
             (forklift, 1.25 kN down-aisle / 2.5 kN cross-aisle at ~400 mm);
      combos ULS proof (pay / placement / accidental / pattern / alternates /
             anchor-uplift) and SLS (sway / top-loaded / alternates), each split
             into X and Y via the per-direction sway imperfection.
    """
    # multi-deep load is PER PALLET: each deep (gap) bay carries one pallet,
    # whose weight is shared by the two side rails (weight_per_pallet / 2 each),
    # applied as a UDL over that bay only — not smeared over the whole rail.
    # The deep (pallet) bays are the rail segments between two frames (odd di);
    # the even-di segments span a single 2-leg frame and carry no pallet.
    w_pallet_half = cfg.weight_per_pallet / 2.0
    z_top = rail_levels[-1]

    # ---- pallet (pay) load arrangements ----------------------------------
    dead = LoadCase("dead", "permanent")
    for mm in m.members.values():
        if mm.member_set in ("rail beams", "rail arms"):
            dead.member_loads.append(MemberLoad(mm.id, qz=-cfg.dead_load_beam))
    m.load_cases["dead"] = dead

    def pallet_case(name, predicate):
        lc = LoadCase(name, "variable")
        for mid_, lane, z, di in rail_members:
            if di % 2 == 1 and predicate(lane, z):     # deep (pallet) bay
                L = m.member_length(m.members[mid_])
                w = w_pallet_half / L if L > 0 else 0.0
                lc.member_loads.append(MemberLoad(mid_, qz=-w))
        return lc

    m.load_cases["pallets"] = pallet_case("pallets", lambda lane, z: True)
    # RSTAB LC12/LC13: alternate lanes loaded (disjoint, union = full)
    alt1 = pallet_case("pallets_alt1", lambda lane, z: lane % 2 == 0)
    alt2 = pallet_case("pallets_alt2", lambda lane, z: lane % 2 == 1)
    # checkerboard lane x level (worst differential sway) and top-level-only
    patt = pallet_case(
        "pallets_pattern",
        lambda lane, z: (lane + rail_levels.index(z)) % 2 == 0)
    top = pallet_case("pallets_top", lambda lane, z: abs(z - z_top) <= _TOL)
    has_pattern = cfg.include_pattern and nL >= 2
    if has_pattern:
        for lc in (alt1, alt2, patt, top):
            m.load_cases[lc.name] = lc

    # ---- placement (0.5 kN) at the front-face top-level upright -----------
    k_load = max(0, min(int(cfg.load_frame), nL))
    front = node_of[(k_load, nDpos - 1, rz(z_top))]
    placement = cfg.include_placement and cfg.placement_load > 0
    if placement:
        px = LoadCase("placement", "variable")
        px.nodal_loads.append(NodalLoad(front, fx=cfg.placement_load))
        m.load_cases["placement"] = px
        py = LoadCase("placement_y", "variable")
        py.nodal_loads.append(NodalLoad(front, fy=cfg.placement_load))
        m.load_cases["placement_y"] = py

    # ---- forklift impact at ~400 mm above base on the front-face upright --
    # (RSTAB LC5/LC6: 1.25 kN down-aisle, 2.5 kN cross-aisle; reuses the SPR
    # accidental_load_x/y + accidental_height, applied at the impact-height node)
    accidental = (cfg.include_accidental
                  and (cfg.accidental_load_x or cfg.accidental_load_y))
    if accidental:
        n_imp = node_of[(k_load, nDpos - 1, rz(acc_h))]
        ix = LoadCase("impact_x", "accidental")
        ix.nodal_loads.append(NodalLoad(n_imp, fx=cfg.accidental_load_x))
        m.load_cases["impact_x"] = ix
        iy = LoadCase("impact_y", "accidental")
        iy.nodal_loads.append(NodalLoad(n_imp, fy=cfg.accidental_load_y))
        m.load_cases["impact_y"] = iy

    # ---- combinations (RSTAB 2.5: per-direction proof + SLS sets) ---------
    gG, gQ = cfg.gamma_G_uls, cfg.gamma_Q
    psi = cfg.pay_placement_factor
    anc = cfg.anchor_placement_factor
    combos: List[Combination] = []
    for d, dirs in (("X", ["+x", "-x"]), ("Y", ["+y", "-y"])):
        plc = "placement" if d == "X" else "placement_y"
        # CO1/CO4 — pay load
        combos.append(Combination(f"ULS-pay-{d}", "ULS",
                                  {"dead": gG, "pallets": gQ}, imp_directions=dirs))
        # CO2/CO5 — placement (psi-reduced pay + placement)
        if placement:
            combos.append(Combination(
                f"ULS-placement-{d}", "ULS",
                {"dead": gG, "pallets": psi, plc: psi}, imp_directions=dirs))
        # CO3/CO6 — accidental (gamma = 1.0 on all actions)
        if accidental:
            ic = "impact_x" if d == "X" else "impact_y"
            combos.append(Combination(
                f"ULS-accidental-{d}", "ULS",
                {"dead": 1.0, "pallets": 1.0, ic: 1.0}, imp_directions=dirs))
        # CO7/CO8 — pattern; alternates
        if has_pattern:
            combos.append(Combination(
                f"ULS-pattern-{d}", "ULS",
                {"dead": gG, "pallets_pattern": gQ}, imp_directions=dirs))
            combos.append(Combination(
                f"ULS-alt1-{d}", "ULS",
                {"dead": gG, "pallets_alt1": gQ}, imp_directions=dirs))
            combos.append(Combination(
                f"ULS-alt2-{d}", "ULS",
                {"dead": gG, "pallets_alt2": gQ}, imp_directions=dirs))
        # CO9/CO10 — anchor / uplift (reduced placement, no pay load)
        if placement:
            combos.append(Combination(
                f"ULS-anchor-{d}", "ULS",
                {"dead": 1.0, plc: anc}, imp_directions=dirs))
        # CO13-CO22 — SLS (now with the sway imperfection)
        combos.append(Combination(f"SLS-sway-{d}", "SLS",
                                  {"dead": 1.0, "pallets": 1.0},
                                  imp_directions=dirs))
        if has_pattern:
            combos.append(Combination(f"SLS-top-{d}", "SLS",
                                      {"dead": 1.0, "pallets_top": 1.0},
                                      imp_directions=dirs))
            combos.append(Combination(f"SLS-alt1-{d}", "SLS",
                                      {"dead": 1.0, "pallets_alt1": 1.0},
                                      imp_directions=dirs))
            combos.append(Combination(f"SLS-alt2-{d}", "SLS",
                                      {"dead": 1.0, "pallets_alt2": 1.0},
                                      imp_directions=dirs))
    m.combinations = combos

    # RSTAB drive-in imperfections: 1/300 down-aisle (X), 1/200 cross-aisle (Y).
    # Honour an explicit user value; otherwise fall back to these drive-in
    # defaults rather than the SPR phi_s (1/350).
    phi_down = cfg.phi_s if cfg.phi_s != 1.0 / 350.0 else 1.0 / 300.0
    phi_cross = cfg.phi_s_cross if cfg.phi_s_cross is not None else 1.0 / 200.0
    m.imperfection = Imperfection(
        n_cols=nL + 1, phi_s=phi_down, phi_s_cross=phi_cross,
        phi_l=cfg.connector_looseness, method="EHF",
        directions=["+x", "-x", "+y", "-y"])


def _checks(m, cfg, nL) -> None:
    m.checks.buckling_sets = ["uprights"]
    m.checks.bolt_d = cfg.bolt_d
    m.checks.bolt_grade = cfg.bolt_grade
    m.checks.bolts_per_connection = cfg.bolts_per_connection
    m.checks.brace_planes = cfg.brace_planes
    m.checks.beam_laterally_restrained = cfg.beam_laterally_restrained
    if getattr(cfg, "built_up_end_columns", False):
        m.built_up = BuiltUpColumn(
            target_set="end columns",
            arrangement=cfg.built_up_arrangement,
            h0=cfg.built_up_h0, panel_a=cfg.built_up_panel,
            L=cfg.frame_height)            # full column buckling length

    if cfg.seismic:
        m.seismic = SeismicSettings(
            enabled=True, zone=cfg.seismic_zone, soil_type=cfg.seismic_soil,
            importance=cfg.seismic_importance,
            response_reduction=cfg.seismic_response_reduction,
            damping=cfg.seismic_damping,
            imposed_factor=cfg.seismic_imposed_factor,
            n_modes=cfg.seismic_n_modes)
