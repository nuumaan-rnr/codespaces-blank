"""Parametric generator for selective pallet racking (SPR) modules -
single-deep or back-to-back, within a row:

  * upright frames braced in the cross-aisle (CA) plane with a D- or
    X-pattern: horizontal strut at `bracing_start` (default 150 mm) above
    the floor, truss diagonals in `bracing_pitch` panels (default 600 mm),
    no intermediate horizontals, one closing horizontal at the last
    diagonal position that fits below the frame top,
  * pallet-beam pairs in the down-aisle direction with semi-rigid
    beam-to-upright connectors, at individually specified beam levels,
  * back-to-back modules: two racks separated by `b2b_gap`, tied with
    row-spacer trusses at every beam level,
  * semi-rigid floor connections - fixed stiffness, or interpolated from
    the master workbook's BASE_STIFFNESS table at the estimated upright
    axial load,
  * pallet loads as UDL on the beam pairs (per module), placement load,
    EN 15512 combinations and sway imperfections.

EN 15512 buckling lengths are assigned automatically to the uprights:
  * major axis (down-aisle bending, local z): the beam gap of the level
    band the segment lies in (floor -> level 1, level 1 -> level 2, ...),
  * minor axis (cross-aisle, local y): the largest unsupported length
    between bracing connection points on that specific upright (for a
    D-pattern the diagonals meet each upright only every other pitch).
Buckling checks are restricted to the uprights (CheckSettings.
buckling_sets); beams are verified for stress / moments / deflection.

Sections are selected by NAME from the section master (CSV/JSON
`SectionLibrary` or .xlsx `MasterWorkbook`), which supplies the full
solver-ready property set; per-section fy values from an .xlsx master are
honoured via dedicated material entries.

Axes: X = down-aisle, Y = cross-aisle, Z = up.
Node ids: frame line i (0..n_bays), upright line s across the CA direction
(single: 0 front / 1 rear; back-to-back: 0..3), elevation index j
(0 = floor): id = i*1000 + s*100 + j.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

from .library import SectionLibrary
from .master_xlsx import MasterWorkbook
from .model import (BasePlate, Combination, Hinge, Imperfection, LoadCase,
                    MemberLoad, NodalLoad, RackModel, Splice, Steel, Support)

_TOL = 1.0     # mm: merge coincident elevations

# standard footplates per upright depth: depth -> (plate X, plate Y) [mm]
STANDARD_FOOTPLATES = {90.0: (100.0, 145.0), 120.0: (100.0, 176.0)}
STANDARD_FOOTPLATE_T = 4.0


def standard_footplate(depth_h: Optional[float]):
    """(b, d, t) of the standard footplate for an upright depth, or None."""
    if depth_h is None:
        return None
    for ref, (b, d) in STANDARD_FOOTPLATES.items():
        if abs(depth_h - ref) <= 5.0:
            return b, d, STANDARD_FOOTPLATE_T
    return None


@dataclass
class LevelSpec:
    """One beam level: its own beam gap, beam section and pallet load.

    gap          : vertical distance from the level below (floor for the
                   first level) [mm]
    beam_section : section name from the master (default: the global
                   beam_section)
    pallet_load  : N per bay at this level PER MODULE (default: the global
                   pallet_load_per_level)
    """

    gap: float
    beam_section: Optional[str] = None
    pallet_load: Optional[float] = None


@dataclass
class RackConfig:
    name: str = "pallet rack"
    # geometry
    module: str = "single"             # 'single' | 'back-to-back'
    n_bays: int = 3
    bay_width: float = 2700.0          # mm beam span (upright centrelines, X)
    depth: float = 1100.0              # mm frame depth (per rack, Y)
    b2b_gap: float = 250.0             # mm gap between back-to-back racks
    beam_levels: List[float] = field(
        default_factory=lambda: [2000.0, 4000.0, 6000.0])   # elevations [mm]
    # per-level definition (preferred): beam gap + beam section + load for
    # EVERY level individually; overrides beam_levels /
    # pallet_load_per_level / beam_section for the levels
    levels: Optional[List[LevelSpec]] = None
    frame_height: Optional[float] = None     # default: top beam level
    # first diagonal connects to the 'outer' (aisle-side) or 'inner'
    # upright of each frame, just above the bottom horizontal; both frames
    # of a back-to-back module are mirrored so the chosen side is the
    # outside on each
    bracing_first_side: str = "outer"
    # cross-aisle frame bracing (see module docstring / drawing)
    bracing_type: str = "D"            # 'D' zigzag | 'X' crossed
    bracing_start: float = 150.0       # first horizontal above floor [mm]
    bracing_pitch: float = 600.0       # diagonal panel height [mm]
    # optional different pattern below the first beam level (e.g. 'X'
    # below level 1 for accidental loads, 'D' above)
    bracing_type_zone1: Optional[str] = None
    # upright splice: auto-placed at H/2 when frame height > splice_above
    # (max manufacturable upright length); set splice_z to position it
    splice_z: Optional[float] = None
    splice_above: float = 11000.0
    splice_bolt_d: float = 12.0
    splice_bolt_grade: str = "4.6"
    splice_rows: int = 2               # bolts along axis per side (pitch p1)
    splice_cols: int = 1               # bolt columns across (pitch p2)
    splice_e1: float = 30.0
    splice_e2: float = 20.0
    splice_p1: float = 60.0
    splice_p2: float = 0.0
    splice_t: Optional[float] = None   # sleeve thickness (default: wall t)
    # sections: names from the master
    library: Optional[SectionLibrary] = None     # default: bundled master
    master: Optional[MasterWorkbook] = None      # .xlsx master (overrides
    #                                              library; provides fy and
    #                                              BASE_STIFFNESS tables)
    upright_section: str = "UP-100x100x2.0"
    beam_section: str = "BM-110x50x1.5"
    brace_section: str = "BR-C40x40x2.0"
    steel_fy: float = 355.0            # MPa (sections without their own fy)
    # connections (from EN 15512 Annex A tests)
    connector_stiffness: float = 1.0e8       # N*mm/rad, about local z
    connector_m_rd: Optional[float] = 2.5e6  # N*mm
    connector_looseness: float = 0.0         # rad (phi_l)
    # floor connection: stiffness [N*mm/rad], 0 = pinned, or 'auto' =
    # interpolate the master's BASE_STIFFNESS table at the estimated
    # upright axial load (requires `master`)
    base_stiffness: Union[float, str] = 5.0e8
    # bracing: analysis-stiffness modification (bolted end-connection
    # flexibility) - strength checks use the full section
    brace_area_factor: float = 0.15
    # bracing end-connection bolts (None disables the BRACE_BOLT check)
    bolt_d: Optional[float] = 12.0          # mm (M12)
    bolt_grade: str = "4.6"
    bolts_per_connection: int = 1
    # footplate / base plate (BASEPLATE check)
    concrete_fck: float = 25.0              # MPa
    plate_fy: float = 250.0                 # MPa
    plate_b: Optional[float] = None         # actual plate [mm] (optional)
    plate_d: Optional[float] = None
    plate_t: Optional[float] = None
    # loads
    pallet_load_per_level: float = 20000.0  # N per bay per level PER MODULE
    dead_load_beam: float = 0.05            # N/mm per beam
    placement_load: float = 500.0           # N horizontal at top (EN 15512)
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance
    mesh_beam: int = 4
    mesh_upright: int = 1                   # per segment between elevations


def bracing_elevations(cfg: RackConfig, frame_height: float) -> List[float]:
    """Elevations of the bracing points: start, start+pitch, ... up to the
    last position that fits at the pitch below the frame top."""
    if cfg.bracing_start > frame_height:
        return []
    zs = [cfg.bracing_start]
    while zs[-1] + cfg.bracing_pitch <= frame_height + _TOL:
        zs.append(zs[-1] + cfg.bracing_pitch)
    return zs


def _pick(lib: SectionLibrary, name: str, role: str) -> str:
    """Section name, falling back to the first master entry of the role."""
    if name in lib.sections:
        return name
    candidates = lib.names(role)
    if not candidates:
        raise KeyError(f"Section '{name}' not in master and no sections "
                       f"with role '{role}' to fall back to")
    return candidates[0]


def build_rack(cfg: RackConfig) -> RackModel:
    lib = cfg.master.library if cfg.master else (cfg.library
                                                 or SectionLibrary.bundled())
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)

    # ---- per-level specification (gap + section + load each) ---------------
    # specs: (elevation, beam section name, pallet load per bay per module)
    if cfg.levels:
        specs: List[Tuple[float, str, float]] = []
        z = 0.0
        for ls in cfg.levels:
            z += ls.gap
            specs.append((z, ls.beam_section or cfg.beam_section,
                          ls.pallet_load if ls.pallet_load is not None
                          else cfg.pallet_load_per_level))
    else:
        specs = [(z, cfg.beam_section, cfg.pallet_load_per_level)
                 for z in sorted(cfg.beam_levels)]
    if not specs:
        raise ValueError("define at least one beam level "
                         "(RackConfig.levels or beam_levels)")

    up = lib.get(_pick(lib, cfg.upright_section, "upright"))
    br = lib.get(_pick(lib, cfg.brace_section, "bracing"))
    beam_secs = {name: lib.get(_pick(lib, name, "beam"))
                 for name in {s for _, s, _ in specs}}
    specs = [(z, _pick(lib, s, "beam"), w) for z, s, w in specs]
    for sec in (up, br, *beam_secs.values()):
        fy = cfg.master.fy.get(sec.name) if cfg.master else None
        if fy:
            mat_name = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat_name, Steel(mat_name, fy=fy))
            sec.material = mat_name
        else:
            sec.material = "steel"
        m.sections[sec.name] = sec

    # ---- upright lines across the CA direction -----------------------------
    # the two frames of a back-to-back module are MIRRORED: on each frame
    # the first diagonal connects to the OUTER (aisle-side) upright just
    # above the bottom horizontal (cfg.bracing_first_side flips this)
    if cfg.module == "back-to-back":
        y_of_side = {0: 0.0, 1: cfg.depth,
                     2: cfg.depth + cfg.b2b_gap,
                     3: 2.0 * cfg.depth + cfg.b2b_gap}
        # (side a, side b, outer side) per frame
        rack_pairs: List[Tuple[int, int, int]] = [(0, 1, 0), (2, 3, 3)]
        spacer_pair: Optional[Tuple[int, int]] = (1, 2)
    elif cfg.module == "single":
        y_of_side = {0: 0.0, 1: cfg.depth}
        rack_pairs = [(0, 1, 0)]
        spacer_pair = None
    else:
        raise ValueError("RackConfig.module must be 'single' or 'back-to-back'")
    sides = sorted(y_of_side)
    if cfg.bracing_first_side not in ("outer", "inner"):
        raise ValueError("bracing_first_side must be 'outer' or 'inner'")
    if cfg.bracing_first_side == "inner":
        rack_pairs = [(sa, sb, sb if outer == sa else sa)
                      for sa, sb, outer in rack_pairs]

    # ---- elevations --------------------------------------------------------
    beam_levels = [z for z, _, _ in specs]
    H = cfg.frame_height if cfg.frame_height else beam_levels[-1]
    if H + _TOL < beam_levels[-1]:
        raise ValueError("frame_height is below the top beam level")
    brace_zs = bracing_elevations(cfg, H)

    # upright splice: explicit elevation or automatic at H/2 when the
    # upright exceeds the maximum manufacturable length
    splice_z = cfg.splice_z
    if splice_z is None and H > cfg.splice_above:
        splice_z = H / 2.0

    zs: List[float] = [0.0]
    extra = {splice_z} if splice_z else set()
    for z in sorted(set(beam_levels) | set(brace_zs) | {H} | extra):
        if z - zs[-1] > _TOL:
            zs.append(z)

    def j_of(z: float) -> int:
        for j, zz in enumerate(zs):
            if abs(zz - z) <= _TOL:
                return j
        raise ValueError(f"elevation {z} not found")

    n_lines = cfg.n_bays + 1
    if len(zs) > 9999:
        raise ValueError("too many distinct elevations for the node id scheme")

    def nid(i: int, s: int, j: int) -> int:
        return i * 100000 + s * 10000 + j

    for i in range(n_lines):
        for s in sides:
            for j, z in enumerate(zs):
                m.add_node(nid(i, s, j), i * cfg.bay_width, y_of_side[s], z)

    # ---- uprights (continuous columns, one member per elevation segment) ---
    mid = 1
    upright_members: Dict[Tuple[int, int], List[int]] = {}
    for i in range(n_lines):
        for s in sides:
            ids = []
            for j in range(len(zs) - 1):
                m.add_member(mid, nid(i, s, j), nid(i, s, j + 1), up.name,
                             member_set="uprights", mesh=cfg.mesh_upright)
                ids.append(mid)
                mid += 1
            upright_members[(i, s)] = ids

    # ---- pallet beams (per upright line) with semi-rigid connectors --------
    # each level uses ITS OWN beam section and pallet load (cfg.levels);
    # connector stiffness / M_Rd / looseness come from the BEAM master per
    # selected beam section, falling back to the cfg values for beams
    # without connector data
    beam_pairs: Dict[float, List[int]] = {}
    looseness_used = [cfg.connector_looseness]
    for z, sec_name, _ in specs:
        sec = m.sections[sec_name]
        k_c = sec.connector_k or cfg.connector_stiffness
        m_rd = sec.connector_m_rd or cfg.connector_m_rd
        loos = (sec.connector_looseness
                if sec.connector_looseness is not None
                else cfg.connector_looseness)
        looseness_used.append(loos)
        j = j_of(z)
        beam_pairs[z] = []
        for i in range(cfg.n_bays):
            for s in sides:
                m.add_member(
                    mid, nid(i, s, j), nid(i + 1, s, j), sec_name,
                    member_set="pallet beams", mesh=cfg.mesh_beam,
                    hinge_i=Hinge(rz=k_c, m_rd_z=m_rd, looseness=loos),
                    hinge_j=Hinge(rz=k_c, m_rd_z=m_rd, looseness=loos))
                beam_pairs[z].append(mid)
                mid += 1

    # ---- cross-aisle frame bracing per rack (see module docstring) ---------
    # brace connection elevations per upright line, for the minor-axis
    # buckling length (includes base and frame top)
    brace_points: Dict[Tuple[int, int], List[float]] = {
        (i, s): [0.0, H] for i in range(n_lines) for s in sides}
    if brace_zs:
        for i in range(n_lines):
            for sa, sb, outer in rack_pairs:
                j0, j1 = j_of(brace_zs[0]), j_of(brace_zs[-1])
                m.add_member(mid, nid(i, sa, j0), nid(i, sb, j0), br.name,
                             mtype="truss", member_set="bracing")
                mid += 1
                for s in (sa, sb):
                    brace_points[(i, s)].append(brace_zs[0])
                if len(brace_zs) > 1:
                    m.add_member(mid, nid(i, sa, j1), nid(i, sb, j1), br.name,
                                 mtype="truss", member_set="bracing")
                    mid += 1
                    for s in (sa, sb):
                        brace_points[(i, s)].append(brace_zs[-1])
                for k in range(len(brace_zs) - 1):
                    ja, jb = j_of(brace_zs[k]), j_of(brace_zs[k + 1])
                    ptype = cfg.bracing_type
                    if cfg.bracing_type_zone1 and \
                            brace_zs[k + 1] <= beam_levels[0] + _TOL:
                        ptype = cfg.bracing_type_zone1
                    if ptype.upper() == "X":
                        m.add_member(mid, nid(i, sa, ja), nid(i, sb, jb),
                                     br.name, mtype="truss",
                                     member_set="bracing")
                        mid += 1
                        m.add_member(mid, nid(i, sb, ja), nid(i, sa, jb),
                                     br.name, mtype="truss",
                                     member_set="bracing")
                        mid += 1
                        for s in (sa, sb):
                            brace_points[(i, s)] += [brace_zs[k],
                                                     brace_zs[k + 1]]
                    else:                                  # 'D' zigzag
                        inner = sb if outer == sa else sa
                        lo, hi = (outer, inner) if k % 2 == 0 \
                            else (inner, outer)
                        m.add_member(mid, nid(i, lo, ja), nid(i, hi, jb),
                                     br.name, mtype="truss",
                                     member_set="bracing")
                        mid += 1
                        brace_points[(i, lo)].append(brace_zs[k])
                        brace_points[(i, hi)].append(brace_zs[k + 1])

    # ---- row spacers between back-to-back racks ----------------------------
    if spacer_pair is not None:
        sa, sb = spacer_pair
        for i in range(n_lines):
            for z in beam_levels:
                j = j_of(z)
                m.add_member(mid, nid(i, sa, j), nid(i, sb, j), br.name,
                             mtype="truss", member_set="row spacers")
                mid += 1

    # ---- EN 15512 buckling lengths for the uprights -------------------------
    # major axis (local z, down-aisle): beam gap of the level band
    bands = [0.0] + beam_levels + ([H] if H - beam_levels[-1] > _TOL else [])

    def band_of(z_mid: float) -> Tuple[float, float]:
        for lo, hi in zip(bands, bands[1:]):
            if lo - _TOL <= z_mid <= hi + _TOL:
                return lo, hi
        return bands[-2], bands[-1]

    # minor axis (local y, cross-aisle): taken FROM THE MODEL per level
    # band - the largest gap between bracing connection points on that
    # upright among the gaps that overlap the band (so e.g. X bracing up
    # to level 1 gives Lcr = pitch there and 2 x pitch for the D zone
    # above, each level seeing its own unsupported length)
    for (i, s), ids in upright_members.items():
        pts = sorted(set(brace_points[(i, s)]))
        gaps = list(zip(pts, pts[1:]))
        for mem_id in ids:
            mem = m.members[mem_id]
            z_mid = (m.nodes[mem.node_i].z + m.nodes[mem.node_j].z) / 2.0
            lo, hi = band_of(z_mid)
            mem.L_buckling_z = hi - lo
            overlapping = [b - a for a, b in gaps
                           if b > lo + _TOL and a < hi - _TOL]
            mem.L_buckling_y = max(overlapping) if overlapping else hi - lo

    # buckling is verified on the uprights only (EN 15512); beams are
    # checked for stress / moments / deflection
    m.checks.buckling_sets = ["uprights"]

    # bracing connection-flexibility modification: only this fraction of
    # the brace area acts in the ANALYSIS (strength checks use full A)
    for mm in m.members.values():
        if mm.member_set in ("bracing", "row spacers"):
            mm.area_factor = cfg.brace_area_factor

    # bracing bolt-connection and footplate checks; when no plate is given
    # the standard footplate for the upright depth is used (90 -> 100x145,
    # 120 -> 100x176, t = 4 mm)
    m.checks.bolt_d = cfg.bolt_d
    m.checks.bolt_grade = cfg.bolt_grade
    m.checks.bolts_per_connection = cfg.bolts_per_connection
    pb, pd_, pt = cfg.plate_b, cfg.plate_d, cfg.plate_t
    if pb is None and pd_ is None and pt is None:
        std = standard_footplate(up.depth_h)
        if std:
            pb, pd_, pt = std
    m.base_plate = BasePlate(f_ck=cfg.concrete_fck, fy_plate=cfg.plate_fy,
                             b=pb, d=pd_, t=pt)

    # upright splice connection check
    if splice_z:
        m.splices.append(Splice(
            z=splice_z, bolt_d=cfg.splice_bolt_d,
            bolt_grade=cfg.splice_bolt_grade,
            rows=cfg.splice_rows, cols=cfg.splice_cols,
            e1=cfg.splice_e1, e2=cfg.splice_e2,
            p1=cfg.splice_p1, p2=cfg.splice_p2, t_sleeve=cfg.splice_t))

    # ---- semi-rigid floor connections ---------------------------------------
    n_uprights = len(sides) * n_lines
    if cfg.base_stiffness == "auto":
        if not cfg.master:
            raise ValueError("base_stiffness='auto' needs an .xlsx master "
                             "with a BASE_STIFFNESS sheet")
        n_modules = len(rack_pairs)
        total_pallets = sum(load for _, _, load in specs)
        N_est = (cfg.gamma_Q * total_pallets * cfg.n_bays
                 * n_modules) / n_uprights
        k_base, _ = cfg.master.base_stiffness(up.name, N_est)
    else:
        k_base = float(cfg.base_stiffness)
    for i in range(n_lines):
        for s in sides:
            k = k_base if k_base > 0 else False
            m.supports.append(Support(nid(i, s, 0), ux=True, uy=True, uz=True,
                                      rx=k, ry=k, rz=False))

    # ---- load cases ---------------------------------------------------------
    dead = LoadCase("dead", "permanent")
    for ids in beam_pairs.values():
        for b in ids:
            dead.member_loads.append(MemberLoad(b, qz=-cfg.dead_load_beam))
    m.load_cases["dead"] = dead

    pallets = LoadCase("pallets", "variable")
    for z, _, load in specs:
        w_line = (load / 2.0) / cfg.bay_width      # UDL per beam line
        for b in beam_pairs[z]:
            pallets.member_loads.append(MemberLoad(b, qz=-w_line))
    m.load_cases["pallets"] = pallets

    top_j = j_of(beam_levels[-1])
    place = LoadCase("placement", "variable")
    place.nodal_loads.append(NodalLoad(nid(0, 0, top_j), fx=cfg.placement_load))
    m.load_cases["placement"] = place

    place_y = LoadCase("placement_y", "variable")
    place_y.nodal_loads.append(NodalLoad(nid(0, 0, top_j), fy=cfg.placement_load))
    m.load_cases["placement_y"] = place_y

    # ---- combinations (EN 15512 defaults - verify for your edition) --------
    m.combinations = [
        Combination("ULS1", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q}),
        Combination("ULS2", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                     "placement": cfg.gamma_Q}),
        Combination("ULS3", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                     "placement_y": cfg.gamma_Q}),
        Combination("SLS1", "SLS",
                    {"dead": 1.0, "pallets": 1.0}, imperfection=False),
        Combination("SLS2", "SLS",
                    {"dead": 1.0, "pallets": 1.0, "placement": 1.0},
                    imperfection=False),
    ]

    # ---- imperfection --------------------------------------------------------
    # phi_l: per EN 15512 the connector looseness may be omitted from phi
    # when modelled in the hinges; the builder's hinges are linear springs
    # without looseness, so the largest looseness of the connectors in use
    # (per-beam from the master, or the cfg fallback) is included here.
    m.imperfection = Imperfection(
        n_cols=n_lines, phi_s=cfg.phi_s, phi_l=max(looseness_used),
        method="EHF", directions=["+x", "-x", "+y", "-y"])

    return m
