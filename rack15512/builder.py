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
                    MemberLoad, NodalLoad, RackModel, SeismicSettings, Splice,
                    Steel, Support)

_TOL = 1.0     # mm: merge coincident elevations


def _selected_bays(n_bays: int, pattern: str) -> List[int]:
    """Bay indices (0..n_bays-1) to brace for the given module pattern."""
    bays = list(range(n_bays))
    p = (pattern or "all").lower()
    if p == "alternate":
        return bays[::2]
    if p == "every_3rd":
        return bays[::3]
    return bays

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
    # cross-aisle X up to a height (seismic): force the CA frame bracing to the
    # X pattern for panels at/below this elevation (None = leave bracing_type)
    ca_x_height: Optional[float] = None
    # ---- seismic bracing (truss members; IS 1893 lateral system) ----------
    # plan bracing: horizontal X across each bay cell, at selected levels;
    # placed only in the spine modules, at most alternate beam levels
    plan_bracing: bool = False
    plan_bracing_section: Optional[str] = "1C36x21x6x1.2"
    plan_bracing_levels: Optional[List[float]] = None     # None = all beam levels
    plan_bracing_modules: str = "alternate"   # 'alternate'|'every_3rd'
    # spine bracing: full-height X tower at the back-to-back centre (or 150 mm
    # behind a single rack), tied to the frame(s) by horizontal frame spacers;
    # X panel per beam level; modules at most alternate
    spine_bracing: bool = False
    spine_bracing_section: Optional[str] = "1C60x40x10x1.6"
    spine_bracing_pitch: Optional[float] = None            # None = bracing_pitch
    spine_bracing_modules: str = "every_3rd"  # 'alternate'|'every_3rd'
    spine_bracing_area_factor: float = 0.15
    spine_offset_single: float = 150.0        # spine offset behind a single rack
    # row / frame spacers (ties): one member_set "frame spacer", modelled as
    # simply-supported truss members (axial only, no flexural stiffness); the
    # section may be a beam section selected by the user
    spacer_section: Optional[str] = None      # None = the frame brace section
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
    brace_planes: int = 1              # shear planes of the brace bolt
    # pallet beams laterally restrained by the unit load (LTB check assumption)
    beam_laterally_restrained: bool = True
    # EN 16681 pallet/unit-load sliding cap (seismic)
    pallet_sliding: bool = False
    pallet_mu: float = 0.37
    # footplate / base plate (BASEPLATE check)
    concrete_fck: float = 25.0              # MPa
    plate_fy: float = 250.0                 # MPa
    plate_b: Optional[float] = None         # actual plate [mm] (optional)
    plate_d: Optional[float] = None
    plate_t: Optional[float] = None
    # footplate anchors (ANCHORAGE check, EN 1992-4 wedge anchor, non-seismic)
    n_anchors: int = 2
    anchor_d: float = 12.0                  # mm (M12)
    anchor_grade: str = "5.6"
    anchor_hef: float = 70.0               # effective embedment [mm]
    anchor_spacing: Optional[float] = None  # lever between anchors [mm]
    anchor_edge: Optional[float] = None     # edge distance [mm] (None = none)
    anchor_pullout_rk: Optional[float] = None  # N_Rk,p [N] (None = default)
    anchor_shear_rk: Optional[float] = None    # V_Rk,c [N] (None = default)
    # loads
    pallet_load_per_level: float = 20000.0  # N per bay per level PER MODULE
    dead_load_beam: float = 0.05            # N/mm per beam
    placement_load: float = 500.0           # N horizontal at top (EN 15512)
    # accidental impact loads on an upright (EN 15512; 0 disables) -
    # applied to the corner upright at accidental_height, combined at
    # gamma = 1.0 with dead + pallet loads (accidental design situation)
    accidental_load_x: float = 1250.0       # N down-aisle
    accidental_load_y: float = 2500.0       # N cross-aisle
    accidental_height: float = 400.0        # mm above floor
    # upright line (frame) index 0..n_bays that carries the placement &
    # accidental loads; for multi-bay runs pick a frame with an add-on
    # connection.  0 = the end (starter) frame.
    load_frame: int = 0
    # switches to drop whole action types from the model + combinations
    include_placement: bool = True          # horizontal placement loads
    include_accidental: bool = True         # accidental impact loads
    include_pattern: bool = True            # checkerboard (pattern) pallet load
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance
    mesh_beam: int = 4
    mesh_upright: int = 1                   # per segment between elevations
    # ---- seismic (IS 1893:2016); see model.SeismicSettings ----------------
    seismic: bool = False
    seismic_zone: str = "III"              # 'II'|'III'|'IV'|'V'
    seismic_soil: str = "II"               # 'I'|'II'|'III'
    seismic_importance: float = 1.0        # I
    seismic_response_reduction: float = 4.0  # R
    seismic_structure_type: str = "Storage rack - cross-aisle braced"
    seismic_damping: float = 0.05
    seismic_imposed_factor: float = 0.8    # kappa: share of pallet (live) load
    #                                        in the seismic weight (W = DL +
    #                                        0.8 LL by default)
    seismic_n_modes: int = 6
    # storey-drift limit Δ/h and P-Δ theta cap (rack values per EN 1998-1 /
    # EN 16681; IS 1893 has no rack-specific code)
    seismic_drift_limit: float = 0.010
    seismic_theta_max: float = 0.30
    # scale the RSA up to the empirical-period base shear (IS 1893 Cl 7.7.3).
    # Off = use the (lower) modal-period base shear directly (departs from the
    # strict clause; sometimes used for flexible long-period racks).
    seismic_scale_base_shear: bool = True

    # ---- multi-deep (drive-in / drive-through / radio-shuttle) --------------
    # system_type "selective" keeps the SPR builder; anything else dispatches to
    # build_drive_in (rack15512/drive_in.py).  All fields backward-compatible.
    system_type: str = "selective"          # "selective" | "drive_in"
    di_variant: str = "drive_in"            # drive_in|drive_through|
    #                                         shuttle_lifo|shuttle_fifo
    n_lanes: int = 3                        # lanes across the width (X)
    lane_width: float = 1350.0              # width per lane (X) [mm]
    n_deep: int = 6                         # pallets deep (Y)
    pallet_depth: float = 1200.0            # pallet depth (Y) [mm]
    deep_clearance: float = 50.0            # clearance per deep position [mm]
    weight_per_pallet: float = 10000.0      # N per pallet
    rail_section: Optional[str] = None      # depth rail / support arm
    arm_section: Optional[str] = None        # cantilever arm (upright -> rail)
    arm_length: float = 200.0                # rail offset into the lane [mm]
    frame_depth: float = 1100.0              # leg spacing within one depth frame
    deep_pitch: Optional[float] = None       # override gap (else pallet+clear)
    level_beam_section: Optional[str] = None  # shuttle: X beam carrying rails
    portal_section: Optional[str] = None    # top-tie / portal beam (X)
    top_beam_section: Optional[str] = None  # access-frame top beam
    end_frame_3upright: bool = False        # opt-in 3-upright reinforced end
    end_frame_section: Optional[str] = None  # heavier end-frame upright
    frame_brace_extent: str = "full"        # "full" | "top"
    plan_every_level: bool = False          # shuttle: plan bracing every level
    spine_position: str = "auto"            # "auto"|"rear"|"centre"|"none"
    tall_frame_threshold: float = 6000.0    # >this → front stability beam
    internal_frame_mode: str = "truncated"  # "truncated" | "full"
    internal_frame_extra: float = 300.0     # truncated uprights above top load
    top_depth_tie: bool = False             # drive-in: depth tie at frame tops
    rail_eccentricity: float = 0.0          # rail-to-upright offset (Y) [mm]
    impact_load: float = 2500.0             # forklift impact (N); 0 disables
    impact_height: float = 400.0            # impact application height [mm]


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
    if getattr(cfg, "system_type", "selective") != "selective":
        from .drive_in import build_drive_in
        return build_drive_in(cfg)
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

    def _bracing_section(name):
        """Resolve a bracing CrossSection; a standard 1C lipped-channel code
        not in the master is generated on the fly (else fall back per role)."""
        if name and name not in lib.sections:
            from .cf_sections import lipped_channel, parse_1c
            dims = parse_1c(name)
            if dims:
                return lipped_channel(name, *dims)
        return lib.get(_pick(lib, name, "bracing"))

    up = lib.get(_pick(lib, cfg.upright_section, "upright"))
    br = _bracing_section(cfg.brace_section)
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

    # EN 15512 accidental impact is applied 400 mm above the floor; a stale or
    # corrupt stored value (e.g. 0.05 from an earlier bug) would otherwise drop
    # the load onto the base node, so fall back to 400 mm when out of range.
    acc_h = cfg.accidental_height
    if not (100.0 <= acc_h < H):
        acc_h = min(400.0, 0.5 * H)

    # upright splice: explicit elevation or automatic at H/2 when the
    # upright exceeds the maximum manufacturable length
    splice_z = cfg.splice_z
    if splice_z is None and H > cfg.splice_above:
        splice_z = H / 2.0

    zs: List[float] = [0.0]
    extra = {splice_z} if splice_z else set()
    if (cfg.accidental_load_x or cfg.accidental_load_y) \
            and 0.0 < acc_h < H:
        extra.add(acc_h)
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
                    if cfg.ca_x_height and \
                            brace_zs[k + 1] <= cfg.ca_x_height + _TOL:
                        ptype = "X"          # seismic CA X up to a height
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

    # ---- row / frame spacers between back-to-back racks --------------------
    # spacers are simply-supported TRUSS ties (axial only, no flexural
    # stiffness); section selectable (default the frame brace), one unified
    # member_set "frame spacer"
    def _register_spacer():
        name = cfg.spacer_section
        if not name:
            return br.name
        for role in ("beam", "bracing"):
            try:
                sec = lib.get(_pick(lib, name, role))
            except (KeyError, ValueError):
                continue
            fy = cfg.master.fy.get(sec.name) if cfg.master else None
            sec.material = (f"steel_fy{fy:.0f}" if fy else "steel")
            if fy:
                m.materials.setdefault(sec.material, Steel(sec.material, fy=fy))
            m.sections[sec.name] = sec
            return sec.name
        return br.name

    spsec = _register_spacer()
    if spacer_pair is not None:
        sa, sb = spacer_pair
        for i in range(n_lines):
            for z in beam_levels:
                j = j_of(z)
                m.add_member(mid, nid(i, sa, j), nid(i, sb, j), spsec,
                             mtype="beam", member_set="frame spacer")
                mid += 1

    # ---- seismic bracing: plan (horizontal) and spine (vertical X) ---------
    def _register_brace(name: Optional[str]):
        """Resolve a bracing section by name (fallback to the frame brace),
        register it on the model, and return its CrossSection name.  Section
        codes of the standard 1C lipped-channel family are generated on the
        fly when not already in the master."""
        if not name:
            return br.name
        sec = _bracing_section(name)
        fy = cfg.master.fy.get(sec.name) if cfg.master else None
        if fy:
            mat_name = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat_name, Steel(mat_name, fy=fy))
            sec.material = mat_name
        else:
            sec.material = "steel"
        m.sections[sec.name] = sec
        return sec.name

    # bays that carry the spine (capped at 'alternate' density); plan bracing
    # is placed only in these modules
    def _cap(pattern: str) -> str:
        return "alternate" if (pattern or "alternate") == "all" else pattern

    spine_bays = (_selected_bays(cfg.n_bays, _cap(cfg.spine_bracing_modules))
                  if cfg.spine_bracing else [])
    _SP = 8                                  # spine upright-line index (>= 4)
    y_spine = (cfg.depth + cfg.b2b_gap / 2.0 if cfg.module == "back-to-back"
               else cfg.depth + cfg.spine_offset_single)
    inner_sides = [1, 2] if spacer_pair else [1]   # frames the spacer ties to
    spine_base_nodes: List[int] = []         # given the same base stiffness

    if cfg.spine_bracing and spine_bays:
        ssec = _register_brace(cfg.spine_bracing_section)
        # spine X-tower in the flue with NO vertical chords.  The X-diagonals
        # are pinned (truss); the spine node sits at the CENTRE of each frame
        # spacer, and that spacer is a beam, so the spacer's flexure ties the
        # spine in-plane and the uprights act as its chords.  Pinned at the
        # base; no spine bracing above the top beam level.
        spine_z = [0.0] + list(beam_levels)
        spine_lines = sorted({i for b in spine_bays for i in (b, b + 1)})
        for i in spine_lines:                # spine node column + base support
            for z in spine_z:
                m.add_node(nid(i, _SP, j_of(z)), i * cfg.bay_width, y_spine, z)
            spine_base_nodes.append(nid(i, _SP, j_of(0.0)))
            for z in spine_z[1:]:            # frame spacer through the spine node
                j = j_of(z)                  # (beam, so it holds the spine in
                for s in inner_sides:        # plane); the spine is its centre
                    m.add_member(mid, nid(i, _SP, j), nid(i, s, j), spsec,
                                 mtype="beam", member_set="frame spacer")
                    mid += 1
        for i in spine_bays:                 # X per beam-level panel (no chords)
            for za, zb in zip(spine_z, spine_z[1:]):
                ja, jb = j_of(za), j_of(zb)
                m.add_member(mid, nid(i, _SP, ja), nid(i + 1, _SP, jb), ssec,
                             mtype="truss", member_set="spine bracing")
                mid += 1
                m.add_member(mid, nid(i + 1, _SP, ja), nid(i, _SP, jb), ssec,
                             mtype="truss", member_set="spine bracing")
                mid += 1

    # plan bracing: only in the spine modules, at most alternate beam levels
    if cfg.plan_bracing and spine_bays:
        psec = _register_brace(cfg.plan_bracing_section)
        plan_z = cfg.plan_bracing_levels or beam_levels[::2]   # alternate
        for i in spine_bays:
            for z in plan_z:
                if not any(abs(zz - z) <= _TOL for zz in zs):
                    continue
                j = j_of(min(zs, key=lambda zz: abs(zz - z)))
                for sa, sb, _o in rack_pairs:
                    m.add_member(mid, nid(i, sa, j), nid(i + 1, sb, j), psec,
                                 mtype="truss", member_set="plan bracing")
                    mid += 1
                    m.add_member(mid, nid(i, sb, j), nid(i + 1, sa, j), psec,
                                 mtype="truss", member_set="plan bracing")
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
    # the brace area acts in the ANALYSIS (strength checks use full A).
    # Row spacers are beams and keep their full section.
    for mm in m.members.values():
        if mm.member_set == "bracing":
            mm.area_factor = cfg.brace_area_factor
        elif mm.member_set in ("plan bracing", "spine bracing"):
            mm.area_factor = cfg.spine_bracing_area_factor

    # bracing bolt-connection and footplate checks; when no plate is given
    # the standard footplate for the upright depth is used (90 -> 100x145,
    # 120 -> 100x176, t = 4 mm)
    m.checks.bolt_d = cfg.bolt_d
    m.checks.bolt_grade = cfg.bolt_grade
    m.checks.bolts_per_connection = cfg.bolts_per_connection
    m.checks.brace_planes = cfg.brace_planes
    m.checks.beam_laterally_restrained = cfg.beam_laterally_restrained
    pb, pd_, pt = cfg.plate_b, cfg.plate_d, cfg.plate_t
    if pb is None and pd_ is None and pt is None:
        std = standard_footplate(up.depth_h)
        if std:
            pb, pd_, pt = std
    # base moment-resistance table MRd(N) from the floor-connection tests
    # (BASE_STIFFNESS sheet) for the partial-restraint check
    m_rd_n = None
    if cfg.master and up.name in cfg.master.base_tables:
        m_rd_n = [(N, m_rd)
                  for N, k_b, m_rd in cfg.master.base_tables[up.name]]
    m.base_plate = BasePlate(
        f_ck=cfg.concrete_fck, fy_plate=cfg.plate_fy, b=pb, d=pd_, t=pt,
        m_rd_n=m_rd_n, n_anchors=cfg.n_anchors, anchor_d=cfg.anchor_d,
        anchor_grade=cfg.anchor_grade, anchor_hef=cfg.anchor_hef,
        anchor_spacing=cfg.anchor_spacing, anchor_edge=cfg.anchor_edge,
        anchor_pullout_rk=cfg.anchor_pullout_rk,
        anchor_shear_rk=cfg.anchor_shear_rk)

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
    # spine tower bases: a pinned floor connection (translations held, free to
    # rotate) for the spine between back-to-back modules / behind a single one
    for node in spine_base_nodes:
        m.supports.append(Support(node, ux=True, uy=True, uz=True,
                                  rx=False, ry=False, rz=False))

    # ---- load cases ---------------------------------------------------------
    dead = LoadCase("dead", "permanent")
    for ids in beam_pairs.values():
        for b in ids:
            dead.member_loads.append(MemberLoad(b, qz=-cfg.dead_load_beam))
    m.load_cases["dead"] = dead

    n_sides = len(sides)
    pallets = LoadCase("pallets", "variable")
    for z, _, load in specs:
        w_line = (load / 2.0) / cfg.bay_width      # UDL per beam line
        for b in beam_pairs[z]:
            pallets.member_loads.append(MemberLoad(b, qz=-w_line))
    m.load_cases["pallets"] = pallets

    # checkerboard (pattern) pallet load: alternate bays AND levels are loaded,
    # the unfavourable arrangement that maximises differential column moments
    # and sway.  Same beam order as beam_pairs (bay outer, side inner).
    pattern = cfg.include_pattern and (cfg.n_bays >= 2 or len(specs) >= 2)
    if pattern:
        patt = LoadCase("pallets_pattern", "variable")
        for lvl_idx, (z, _, load) in enumerate(specs):
            w_line = (load / 2.0) / cfg.bay_width
            for k, b in enumerate(beam_pairs[z]):
                bay = k // n_sides
                if (bay + lvl_idx) % 2 == 0:
                    patt.member_loads.append(MemberLoad(b, qz=-w_line))
        if patt.member_loads:
            m.load_cases["pallets_pattern"] = patt
        else:
            pattern = False

    # the frame (upright line) carrying the placement & accidental loads
    li = max(0, min(int(cfg.load_frame), cfg.n_bays))

    top_j = j_of(beam_levels[-1])
    placement = cfg.include_placement and cfg.placement_load > 0
    if placement:
        place = LoadCase("placement", "variable")
        place.nodal_loads.append(NodalLoad(nid(li, 0, top_j),
                                           fx=cfg.placement_load))
        m.load_cases["placement"] = place
        place_y = LoadCase("placement_y", "variable")
        place_y.nodal_loads.append(NodalLoad(nid(li, 0, top_j),
                                             fy=cfg.placement_load))
        m.load_cases["placement_y"] = place_y

    # accidental impact loads on the chosen frame's upright (EN 15512)
    acc = (cfg.include_accidental
           and (cfg.accidental_load_x or cfg.accidental_load_y)
           and 0.0 < acc_h < H)
    if acc:
        j_acc = j_of(acc_h)
        acc_x = LoadCase("accidental_x", "accidental")
        acc_x.nodal_loads.append(NodalLoad(nid(li, 0, j_acc),
                                           fx=cfg.accidental_load_x))
        m.load_cases["accidental_x"] = acc_x
        acc_y = LoadCase("accidental_y", "accidental")
        acc_y.nodal_loads.append(NodalLoad(nid(li, 0, j_acc),
                                           fy=cfg.accidental_load_y))
        m.load_cases["accidental_y"] = acc_y

    # ---- combinations (EN 15512 defaults - verify for your edition) --------
    m.combinations = [
        Combination("ULS1", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q}),
        Combination("SLS1", "SLS",
                    {"dead": 1.0, "pallets": 1.0}, imperfection=False),
    ]
    if placement:
        m.combinations.insert(1, Combination(
            "ULS2", "ULS", {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                            "placement": cfg.gamma_Q}))
        m.combinations.insert(2, Combination(
            "ULS3", "ULS", {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                            "placement_y": cfg.gamma_Q}))
        m.combinations.append(Combination(
            "SLS2", "SLS", {"dead": 1.0, "pallets": 1.0, "placement": 1.0},
            imperfection=False))
    if acc:
        # accidental design situation: gamma = 1.0 on all actions
        idx = len([c for c in m.combinations if c.kind == "ULS"])
        m.combinations.insert(idx, Combination(
            "ULS-accX", "ULS",
            {"dead": 1.0, "pallets": 1.0, "accidental_x": 1.0},
            imp_directions=["+x"]))
        m.combinations.insert(idx + 1, Combination(
            "ULS-accY", "ULS",
            {"dead": 1.0, "pallets": 1.0, "accidental_y": 1.0},
            imp_directions=["+y"]))
    if pattern:
        # checkerboard pallet arrangement (unfavourable partial loading)
        idx = len([c for c in m.combinations if c.kind == "ULS"])
        m.combinations.insert(idx, Combination(
            "ULS-pattern", "ULS",
            {"dead": cfg.gamma_G, "pallets_pattern": cfg.gamma_Q}))

    # ---- imperfection --------------------------------------------------------
    # phi_l: per EN 15512 the connector looseness may be omitted from phi
    # when modelled in the hinges; the builder's hinges are linear springs
    # without looseness, so the largest looseness of the connectors in use
    # (per-beam from the master, or the cfg fallback) is included here.
    m.imperfection = Imperfection(
        n_cols=n_lines, phi_s=cfg.phi_s, phi_l=max(looseness_used),
        method="EHF", directions=["+x", "-x", "+y", "-y"])

    # ---- seismic settings (IS 1893) -----------------------------------------
    if cfg.seismic:
        m.seismic = SeismicSettings(
            enabled=True, zone=cfg.seismic_zone, soil_type=cfg.seismic_soil,
            importance=cfg.seismic_importance,
            response_reduction=cfg.seismic_response_reduction,
            structure_type=cfg.seismic_structure_type,
            damping=cfg.seismic_damping,
            imposed_factor=cfg.seismic_imposed_factor,
            n_modes=cfg.seismic_n_modes,
            drift_limit_ratio=cfg.seismic_drift_limit,
            theta_max=cfg.seismic_theta_max,
            apply_base_shear_scaling=cfg.seismic_scale_base_shear,
            pallet_sliding=cfg.pallet_sliding, pallet_mu=cfg.pallet_mu)

    return m
