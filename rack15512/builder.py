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
from .model import (BasePlate, Combination, Hinge, Imperfection, Link, LoadCase,
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


def _bolt_slip_stiffness(d: float, fub: float, fu: float,
                         t_up: Optional[float], t_st: Optional[float],
                         e1: Optional[float]) -> float:
    """Per-bolt shear-connection (slip) stiffness [N/mm] for the upright<->
    stiffener interface, EN 1993-1-8 component method (the E cancels): bolt
    shear in series with bearing on each connected ply."""
    d_m16 = 16.0
    k_shear = 16.0 * d * d * fub / d_m16             # bolt shear

    def k_bear(t: float) -> float:
        kb = min(0.25 * e1 / d + 0.5, 1.25) if e1 else 1.0
        kt = min(1.5 * t / d_m16, 2.5)
        return 24.0 * kb * kt * d * fu

    parts = [k_shear]
    if t_up:
        parts.append(k_bear(t_up))
    if t_st:
        parts.append(k_bear(t_st))
    return 1.0 / sum(1.0 / p for p in parts if p > 0)


def _closed_upright_section(name, up):
    """Type-1 stiffener closes the upright's open face -> a closed cell.  Make the
    closed-section credit physically consistent for the flexural-torsional check
    (EN 15512 9.7.5):

      * St-Venant torsion is much larger (Bredt: It = 4*Am^2 / (perimeter/t)) and
        now dominates Ncr,T;
      * a closed cell warps very little, so the warping constant Iw collapses to a
        small fraction of the open value;
      * the shear centre moves onto (near) the centroid, so y0 -> 0 and the
        flexural-torsional coupling decouples (i0^2 = (Iy+Iz)/A).

    Only It_gross/Iw_gross/y0 (the FT inputs) change; the flexural section
    properties (A, Iy, Iz, section moduli) are unchanged because the thin closing
    lip adds negligible bending area on the upright's own centroid line - that
    composite gain is carried by the separate stiffener member, not here."""
    from dataclasses import replace
    h = up.depth_h or 100.0
    b = up.width_b or 100.0
    t = up.t or 2.0
    it_closed = 4.0 * (h * b) ** 2 / (2.0 * (h + b) / t)
    it = max(it_closed, up.It_gross or up.J or 1.0)
    # closed cell: warping is negligible (~a few % of the open lipped channel).
    iw_closed = (up.Iw_gross * 0.05) if up.Iw_gross else up.Iw_gross
    return replace(up, name=name, It_gross=it, J=max(it, up.J),
                   Iw_gross=iw_closed, y0=0.0)


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
    # CA bracing zones (seismic): list of (up_to_height_mm, n_diagonals) so the
    # lower frame zones can carry MORE cross-aisle diagonals per panel.  The
    # base X is at offset 0; each extra pair is a real X offset +100 mm (new
    # upright nodes).  A panel uses the first zone whose up_to_height >= its top;
    # panels above every zone keep the normal D/X pattern.  () = disabled.
    ca_brace_zones: Tuple[Tuple[float, int], ...] = ()
    # ---- seismic bracing (truss members; IS 1893 lateral system) ----------
    # plan bracing: horizontal X across each bay cell, at selected levels;
    # placed only in the spine modules, at most alternate beam levels
    plan_bracing: bool = False
    plan_bracing_section: Optional[str] = "1C36x21x6x1.2"
    plan_bracing_levels: Optional[List[float]] = None     # None = all beam levels
    plan_bracing_modules: str = "alternate"   # 'all'|'alternate'|'every_3rd'
    plan_bracing_type: str = "D"              # 'D' single diagonal | 'X' crossed
    # specific modules (lane indices) to plan-brace; overrides the mode above
    plan_bracing_module_list: Optional[List[int]] = None
    # spine bracing: full-height X tower at the back-to-back centre (or 150 mm
    # behind a single rack), tied to the frame(s) by horizontal frame spacers;
    # X panel per beam level; modules at most alternate
    spine_bracing: bool = False
    spine_bracing_section: Optional[str] = "1C60x40x10x1.6"
    spine_bracing_pitch: Optional[float] = None            # None = bracing_pitch
    spine_bracing_modules: str = "every_3rd"  # 'all'|'alternate'|'every_3rd'
    # specific bays (lane indices) to spine-brace; overrides the mode above
    spine_bracing_module_list: Optional[List[int]] = None
    spine_bracing_area_factor: float = 0.15
    spine_offset_single: float = 150.0        # spine offset behind a single rack
    # row / frame spacers (ties): one member_set "frame spacer", modelled as
    # simply-supported truss members (axial only, no flexural stiffness); the
    # section may be a beam section selected by the user
    spacer_section: Optional[str] = None      # None = the frame brace section
    # frame-spacer vertical placement (industry standard): one tie every
    # spacer_spacing up the frame, a mandatory tie spacer_top_offset below the
    # top, and at least spacer_min ties
    spacer_spacing: float = 2400.0            # [mm]
    spacer_top_offset: float = 200.0          # [mm] below frame height
    spacer_min: int = 2
    # upright splice: auto-placed at H/2 when frame height > splice_above
    # (max manufacturable upright length); set splice_z to position it
    splice_z: Optional[float] = None
    splice_above: float = 11500.0
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
    # upright stiffener: a bolted C-section reinforcement acting as a PARTIAL-
    # COMPOSITE built-up member.  Modelled as a SEPARATE member on its own
    # centroid line (offset from the upright), tied to the upright at bolt rows
    # by interface links (transverse stiff = deflect together; vertical = bolt
    # shear stiffness, so the axial transfers by shear flow, never a flat 50%).
    # The offset captures the CG shift.  type 1 = C closing the open face
    # (inside), type 2 = C on the outer face.  None / reinforce_height = 0 off.
    stiffener_section: Optional[str] = None
    reinforce_height: float = 0.0      # [mm]; reinforce segments with top <= this
    stiffener_offset: float = 30.0     # [mm]; upright<->stiffener centroid gap
    stiffener_type: int = 1            # 1 = closing/inside, 2 = outer face
    # interface (bolt) shear stiffness: auto-derived from the bolt by the
    # EN 1993-1-8 component method when None; a number overrides it [N/mm]
    stiffener_shear_k: Optional[float] = None
    stiffener_bolt_d: float = 8.0      # interface bolt diameter [mm] (M8)
    stiffener_bolt_grade: str = "8.8"
    stiffener_bolts_per_row: int = 1   # bolts per bolt row
    stiffener_bolt_pitch: float = 600.0  # [mm] bolt interval up the height
    steel_fy: float = 355.0            # MPa (sections without their own fy)
    # when True, use steel_fy for EVERY section (ignore the master's per-section
    # fy) - lets the material yield be set from the input for any master
    fy_override: bool = False
    # connections (from EN 15512 Annex A tests)
    connector_stiffness: float = 1.0e8       # N*mm/rad, about local z
    connector_m_rd: Optional[float] = 2.5e6  # N*mm
    connector_looseness: float = 0.0         # rad (phi_l)
    # floor connection: explicit stiffness [N*mm/rad] (0 = pinned), or the
    # default 'auto' = interpolate the master's tested BASE_STIFFNESS table at
    # the estimated upright axial load (EN 15512).  With no master 'auto' falls
    # back to: selective -> 5.0e8; drive-in -> calculated from the R899 formulas
    # (rack15512.base_stiffness).
    base_stiffness: Union[float, str] = "auto"
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
    # applied to the load_frame upright (an interior line by default) at
    # accidental_height, combined at gamma = 1.0 with dead + pallet loads
    # (accidental design situation)
    accidental_load_x: float = 1250.0       # N down-aisle
    accidental_load_y: float = 2500.0       # N cross-aisle
    accidental_height: float = 400.0        # mm above floor
    # upright line (frame) index 0..n_bays that carries the placement &
    # accidental loads.  None (default) -> the governing INTERIOR upright line
    # (shared between two bays, ~twice the axial of an end column), matching
    # RSTAB/EN 15512 practice of loading an inner frame, not the corner/edge;
    # falls back to the only (end) line for a single-bay run.  An explicit
    # int still pins a specific line (0 = the end/starter frame).
    load_frame: Optional[int] = None
    # switches to drop whole action types from the model + combinations
    include_placement: bool = True          # horizontal placement loads
    include_accidental: bool = True         # accidental impact loads
    include_pattern: bool = True            # checkerboard (pattern) pallet load
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance (down-aisle)
    phi_s_cross: Optional[float] = None     # cross-aisle out-of-plumb; None=phi_s
    # 'EN15512' -> phi = sqrt(0.5+1/n)*(2*phi_s+phi_l) (amplified rack value);
    # 'EN1993'  -> phi = phi_s directly (plain out-of-plumb, e.g. 1/300; RSTAB-style)
    imperfection_standard: str = "EN15512"
    # design-stiffness reduction E/gamma_M1 for the 2nd-order stability analysis
    # (EN 1993-1-1 / EN 15512; RSTAB "Materials (partial factor gamma_M)").
    # 1.0 = full stiffness; 1.1 = E/1.1 (gamma_M1).
    stiffness_gamma_m: float = 1.0
    # EN 1993-1-1 5.3.2(3) reduction phi = phi_s * alpha_h * alpha_m (RSTAB's
    # "Calculate value of inclination"); only with imperfection_standard='EN1993'.
    # alpha_h from the frame height, alpha_m from the columns in a row (n_cols).
    imperfection_alpha_hm: bool = False
    imperfection_method: str = "EHF"        # 'EHF' notional forces | 'geometry'
    # explicit beam-to-upright connector stiffness [N*mm/rad]; when set it
    # overrides the per-section master value (use to match a specific test/solver)
    connector_stiffness_override: Optional[float] = None
    # model the connector looseness (free-play) DIRECTLY as a rotational dead-band
    # in the connector spring (EN 15512), instead of the default of lumping it
    # into the sway imperfection phi_l.  Needs the 2nd-order nonlinear solver.
    model_connector_looseness: bool = False
    # optional NONLINEAR connector moment-rotation diagram (semi-rigid hinge
    # nonlinearity, RSTAB-style): [[phi_rad, M_Nmm], ...] for phi>=0.  When set it
    # replaces the linear connector spring on every pallet-beam end.
    connector_moment_rotation: Optional[List[List[float]]] = None
    # plastic (Hysteretic) connector law: elastic to the connector moment
    # capacity (connector_m_rd), then hardening - for pushover / loading the
    # connection past its capacity.  Needs the 2nd-order nonlinear solver.
    connector_plastic: bool = False
    connector_hardening: float = 0.02      # post-yield stiffness ratio
    connector_phi_u: float = 0.05          # ultimate connector rotation [rad]
    # nonlinear axial-dependent base: [[P_kN, C_Nmm_per_rad], ...] giving the base
    # ROTATIONAL stiffness as a function of column compression (RSTAB-style; 0 at
    # uplift = tearing).  When set, the engine iterates the base spring to match.
    base_axial_table: Optional[List[List[float]]] = None
    # drive-in ULS factors (RSTAB scheme): gamma_G for ULS proof combos, the
    # psi-reduced factor on simultaneous pay+placement, and the placement factor
    # for the anchor/uplift combos (1.0 DL + anchor_placement_factor*placement)
    gamma_G_uls: float = 1.35
    pay_placement_factor: float = 1.26
    anchor_placement_factor: float = 0.4
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
    # number of 2-leg depth frames distributed over the lane depth (the gap
    # between frames is auto-computed: gap = (lane_deep - n_frames*frame_depth)
    # / (n_frames-1)).  Independent of n_deep (which sets the storage envelope
    # lane_deep = pallet_depth*n_deep + (n_deep+1)*deep_clearance and the load).
    n_frames: int = 2
    weight_per_pallet: float = 10000.0      # N per pallet
    # vertical level spacing is pallet-driven: each bay (rail) level gap =
    # pallet_height + level_clearance; the top beam sits top_beam_gap above the
    # last bay level (these populate cfg.levels / frame_height from the form)
    pallet_height: float = 1200.0           # pallet height (Z) [mm]
    level_clearance: float = 200.0          # added per level for the beam [mm]
    top_beam_gap: float = 1400.0            # top beam level above the last bay [mm]
    rail_section: Optional[str] = None      # depth rail / support arm
    arm_section: Optional[str] = None        # cantilever arm (upright -> rail)
    arm_length: float = 200.0                # rail offset into the lane [mm]
    # cantilever arm-to-upright bracket connector (RSTAB Konsole hinge: jZ =
    # 100 kN.cm/rad = 1.0e6 N.mm/rad about local z)
    arm_connector_stiffness: float = 1.0e6   # N*mm/rad
    arm_connector_m_rd: Optional[float] = None  # N*mm
    frame_depth: float = 1100.0              # leg spacing within one depth frame
    deep_pitch: Optional[float] = None       # override gap (else pallet+clear)
    level_beam_section: Optional[str] = None  # shuttle: X beam carrying rails
    portal_section: Optional[str] = None    # top-tie / portal beam (X), top level
    top_beam_section: Optional[str] = None  # access-frame top beam
    # rear (back) down-aisle beams - separate section + connector from the top
    # beams so the two can differ
    back_beam_section: Optional[str] = None
    top_connector_stiffness: Optional[float] = None   # override top-beam connector
    back_connector_stiffness: Optional[float] = None  # override back-beam connector
    end_frame_3upright: bool = False        # opt-in 3-upright reinforced end
    end_frame_section: Optional[str] = None  # heavier end-frame upright
    frame_brace_extent: str = "full"        # "full" | "top"
    plan_every_level: bool = False          # shuttle: plan bracing every level
    spine_position: str = "auto"            # "auto"|"rear"|"centre"|"none"
    tall_frame_threshold: float = 6000.0    # >this → front stability beam
    internal_frame_mode: str = "truncated"  # "truncated" | "full"
    internal_frame_extra: float = 300.0     # truncated uprights above top load
    top_depth_tie: bool = True              # drive-in: depth tie (beam) at frame tops
    rail_eccentricity: float = 0.0          # rail-to-upright offset (Y) [mm]
    impact_load: float = 2500.0             # deprecated: superseded by
    impact_height: float = 400.0            # accidental_load_x/y + accidental_height
    #                                         (kept only for config back-compat)
    # built-up (battened/laced) boxed end columns — EN 1993-1-1 §6.4 check
    built_up_end_columns: bool = False      # opt-in: boxed end-frame uprights
    built_up_arrangement: str = "battened"  # "battened" | "laced"
    built_up_h0: float = 100.0              # chord centroid spacing [mm]
    built_up_panel: float = 500.0           # batten / lacing panel spacing [mm]


def bracing_elevations(cfg: RackConfig, frame_height: float) -> List[float]:
    """Elevations of the bracing points: start, start+pitch, ... up to the
    last position that fits at the pitch below the frame top."""
    if cfg.bracing_start > frame_height:
        return []
    zs = [cfg.bracing_start]
    while zs[-1] + cfg.bracing_pitch <= frame_height + _TOL:
        zs.append(zs[-1] + cfg.bracing_pitch)
    return zs


def frame_spacer_levels(cfg: RackConfig, frame_height: float) -> List[float]:
    """Frame-spacer (row-tie) elevations per industry standard: one tie every
    `spacer_spacing` up the frame, a mandatory tie `spacer_top_offset` below the
    top, and at least `spacer_min` ties."""
    spacing = max(cfg.spacer_spacing, 1.0)
    top = max(frame_height - cfg.spacer_top_offset, 0.0)
    zs: List[float] = []
    z = spacing
    while z < top - 0.5 * spacing:            # keep clear of the mandatory top tie
        zs.append(z)
        z += spacing
    if top > _TOL:
        zs.append(top)
    # enforce the minimum number of ties (halve down from the lowest)
    while zs and len(zs) < max(cfg.spacer_min, 1):
        zs.insert(0, zs[0] / 2.0)
    return sorted({round(v, 1) for v in zs if v > _TOL})


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
        fy = (cfg.master.fy.get(sec.name) if (cfg.master and not cfg.fy_override) else None)
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

    # frame-spacer (row-tie) elevations: industry standard, not at every beam
    # level (used only when the module has a back-to-back spacer pair)
    spacer_zs = frame_spacer_levels(cfg, H) if spacer_pair is not None else []

    # CA bracing zones: number of cross-aisle diagonals per panel, and the extra
    # nodes for the +100 mm offset diagonals (real geometry).
    CA_BRACE_OFFSET = 100.0

    def _ca_zone_count(z_top: float) -> Optional[int]:
        for up_to, cnt in sorted(cfg.ca_brace_zones):
            if z_top <= up_to + _TOL:
                return max(int(cnt), 1)
        return None

    ca_extra: set = set()
    if cfg.ca_brace_zones:
        for k in range(len(brace_zs) - 1):
            n = _ca_zone_count(brace_zs[k + 1])
            if not n or n < 2:
                continue
            for d in range(n):
                o = (d // 2) * CA_BRACE_OFFSET
                if o == 0:
                    continue
                zt = brace_zs[k + 1] + o
                if zt > H + _TOL:
                    continue
                ca_extra.add(brace_zs[k] + o)
                ca_extra.add(zt)

    zs: List[float] = [0.0]
    extra = {splice_z} if splice_z else set()
    extra |= ca_extra
    if (cfg.accidental_load_x or cfg.accidental_load_y) \
            and 0.0 < acc_h < H:
        extra.add(acc_h)
    extra |= set(spacer_zs)
    # node exactly at the stiffener reinforce boundary so the straddling upright
    # segment is split there (lower part reinforced, upper part not)
    if cfg.stiffener_section and cfg.reinforce_height > _TOL:
        extra.add(min(cfg.reinforce_height, H))
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
        # connector stiffness resolves by the upright wall thickness it bolts to
        # (beam-stiffness import), else the section's connector_k / cfg default;
        # an explicit override (to match a test / external solver) wins.
        k_c = (cfg.connector_stiffness_override
               or sec.connector_k_for(up.t) or cfg.connector_stiffness)
        m_rd = sec.connector_m_rd or cfg.connector_m_rd
        loos = (sec.connector_looseness
                if sec.connector_looseness is not None
                else cfg.connector_looseness)
        looseness_used.append(loos)            # always recorded on the hinge
        j = j_of(z)
        beam_pairs[z] = []
        for i in range(cfg.n_bays):
            for s in sides:
                mphi = cfg.connector_moment_rotation

                def _conn():
                    return Hinge(rz=k_c, m_rd_z=m_rd, looseness=loos, m_phi_z=mphi,
                                 plastic=cfg.connector_plastic,
                                 hardening=cfg.connector_hardening,
                                 phi_u=cfg.connector_phi_u)
                m.add_member(
                    mid, nid(i, s, j), nid(i + 1, s, j), sec_name,
                    member_set="pallet beams", mesh=cfg.mesh_beam,
                    hinge_i=_conn(), hinge_j=_conn())
                beam_pairs[z].append(mid)
                mid += 1

    # ---- cross-aisle frame bracing per rack (see module docstring) ---------
    # brace connection elevations per upright line, for the minor-axis
    # buckling length (includes base and frame top)
    brace_points: Dict[Tuple[int, int], List[float]] = {
        (i, s): [0.0, H] for i in range(n_lines) for s in sides}
    if brace_zs:
        # X-brace "up to a level" extends one full panel above the panel that
        # crosses the chosen elevation: x_top = first bracing node at/above the
        # level; a panel is X when its BOTTOM node is <= x_top.
        x_top = None
        if cfg.ca_x_height:
            _above = [z for z in brace_zs if z >= cfg.ca_x_height - _TOL]
            x_top = _above[0] if _above else brace_zs[-1]
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
                    # CA bracing zone override: n_z diagonals per panel, an X at
                    # offset 0 and each extra pair a real X offset +100 mm
                    n_z = _ca_zone_count(brace_zs[k + 1])
                    if n_z is not None:
                        for d in range(n_z):
                            o = (d // 2) * CA_BRACE_OFFSET
                            zb, zt = brace_zs[k] + o, brace_zs[k + 1] + o
                            if zt > H + _TOL:
                                break
                            jb_, jt_ = j_of(zb), j_of(zt)
                            if d % 2 == 0:
                                m.add_member(mid, nid(i, sa, jb_),
                                             nid(i, sb, jt_), br.name,
                                             mtype="truss", member_set="bracing")
                            else:
                                m.add_member(mid, nid(i, sb, jb_),
                                             nid(i, sa, jt_), br.name,
                                             mtype="truss", member_set="bracing")
                            mid += 1
                            brace_points[(i, sa)] += [zb, zt]
                            brace_points[(i, sb)] += [zb, zt]
                        continue
                    ja, jb = j_of(brace_zs[k]), j_of(brace_zs[k + 1])
                    ptype = cfg.bracing_type
                    if cfg.bracing_type_zone1 and \
                            brace_zs[k + 1] <= beam_levels[0] + _TOL:
                        ptype = cfg.bracing_type_zone1
                    if x_top is not None and brace_zs[k] <= x_top + _TOL:
                        ptype = "X"          # X up to one panel above the level
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
            fy = (cfg.master.fy.get(sec.name) if (cfg.master and not cfg.fy_override) else None)
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
            for z in spacer_zs:              # industry std: every ~2400 mm + top
                j = j_of(z)
                m.add_member(mid, nid(i, sa, j), nid(i, sb, j), spsec,
                             mtype="beam", member_set="frame spacer")
                mid += 1

    # upright stiffener: register the separate reinforcement section (role
    # 'upright'); the offset member + interface links are built after the
    # buckling-length loop below.
    def _register_stiffener():
        name = cfg.stiffener_section
        if not name or cfg.reinforce_height <= _TOL:
            return None
        sec = lib.get(_pick(lib, name, "upright"))
        fy = (cfg.master.fy.get(sec.name)
              if (cfg.master and not cfg.fy_override) else None)
        if fy:
            mat_name = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat_name, Steel(mat_name, fy=fy))
            sec.material = mat_name
        else:
            sec.material = "steel"
        m.sections[sec.name] = sec
        return sec.name

    stiff_name = _register_stiffener()

    # ---- seismic bracing: plan (horizontal) and spine (vertical X) ---------
    def _register_brace(name: Optional[str]):
        """Resolve a bracing section by name (fallback to the frame brace),
        register it on the model, and return its CrossSection name.  Section
        codes of the standard 1C lipped-channel family are generated on the
        fly when not already in the master."""
        if not name:
            return br.name
        sec = _bracing_section(name)
        fy = (cfg.master.fy.get(sec.name) if (cfg.master and not cfg.fy_override) else None)
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

    # RSTAB-style member-set names: one continuous set per upright line per
    # storey segment (base->L1, L1->L2, ..., topbeam->top); the set length is
    # the down-aisle buckling length Lcr,DA assigned just below.
    def _seg_name(lo: float, hi: float) -> str:
        bi = bands.index(lo)
        lo_name = "base" if bi == 0 else f"L{bi}"
        if abs(hi - H) < _TOL and (not beam_levels or hi - beam_levels[-1] > _TOL):
            hi_name = "top"
        else:
            hi_name = f"L{bi + 1}"
        return f"{lo_name}→{hi_name}"

    def _line_label(i: int, s: int) -> str:
        col = chr(65 + i) if i < 26 else f"C{i + 1}"
        return f"{col}{s + 1}"

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
            mem.set_label = f"Upright {_line_label(i, s)} · {_seg_name(lo, hi)}"
            overlapping = [b - a for a, b in gaps
                           if b > lo + _TOL and a < hi - _TOL]
            mem.L_buckling_y = max(overlapping) if overlapping else hi - lo

    # upright stiffener: a SEPARATE member on its own centroid line (offset from
    # the upright per type), tied to the upright at each bolt row by interface
    # links - transverse stiff (deflect together, share bending) and a finite
    # vertical bolt-shear stiffness (axial transfers by shear flow: partial
    # composite, shear-lag from the free top, never a flat 50%).  The offset
    # captures the CG shift; each member reports its own N, My, Mz.
    if stiff_name:
        rh = min(cfg.reinforce_height, H)
        SNID = 8_000_000
        K_TRANS = 1.0e8                       # stiff transverse tie [N/mm]
        st_sec = m.sections[stiff_name]
        # interface bolt shear stiffness: explicit per-link override, else
        # auto-derived per bolt (EN 1993-1-8 component method) and spread along
        # the height by the BOLT PITCH (closer bolts -> stiffer -> more composite)
        if cfg.stiffener_shear_k is not None:
            kz_fixed, kz_per_mm = max(cfg.stiffener_shear_k, 1.0), None
        else:
            fub = 100.0 * int(str(cfg.stiffener_bolt_grade).split(".")[0])
            fu_up = up.fu or 1.25 * cfg.steel_fy
            k_single = _bolt_slip_stiffness(
                cfg.stiffener_bolt_d, fub, fu_up, up.t or 2.0,
                st_sec.t or 2.0, up.e1 or 1.5 * cfg.stiffener_bolt_d)
            kz_fixed = None
            kz_per_mm = (max(int(cfg.stiffener_bolts_per_row), 1) * k_single
                         / max(cfg.stiffener_bolt_pitch, 1.0))
        # type 1 closes the open face -> a closed-section torsion credit on the
        # reinforced upright segments (improves flexural-torsional buckling)
        up_zone_section = up.name
        if cfg.stiffener_type == 1:
            closed = _closed_upright_section(f"{up.name}~closed", up)
            m.sections[closed.name] = closed
            up_zone_section = closed.name
        partner: Dict[int, int] = {}
        for _sa, _sb, _o in rack_pairs:
            partner[_sa] = _sb
            partner[_sb] = _sa
        zone_js = [j for j, z in enumerate(zs) if z <= rh + _TOL]
        for (i, s), ids in upright_members.items():
            # closed-section torsion credit (type 1) on the reinforced segments
            if up_zone_section != up.name:
                for u in ids:
                    um0 = m.members[u]
                    if max(m.nodes[um0.node_i].z,
                           m.nodes[um0.node_j].z) <= rh + _TOL:
                        um0.section = up_zone_section
            ps = partner.get(s, s)
            interior = 1.0 if y_of_side[ps] >= y_of_side[s] else -1.0
            # offset magnitude: the selected stiffener's own mounted centroid gap
            # (from the master) when given, else the global config value
            off = (st_sec.mount_offset if st_sec.mount_offset is not None
                   else cfg.stiffener_offset)
            dy = (interior if cfg.stiffener_type == 1 else -interior) * off
            x_up = i * cfg.bay_width
            for j in zone_js:                 # offset stiffener nodes
                m.add_node(SNID + nid(i, s, j), x_up, y_of_side[s] + dy, zs[j])
            up_by_lo = {round(min(m.nodes[m.members[u].node_i].z,
                                  m.nodes[m.members[u].node_j].z), 3): m.members[u]
                        for u in ids}
            for ja, jb in zip(zone_js, zone_js[1:]):   # stiffener column members
                um = up_by_lo.get(round(zs[ja], 3))
                seg = zs[jb] - zs[ja]
                # the stiffener is tied to the upright transversely at every bolt
                # row (the stiff kx/ky interface links), so its buckling length is
                # the bolt pitch (this segment), NOT the upright storey length; and
                # it is reported as its OWN set, not lumped into the upright row.
                slabel = (("Stiffener " + um.set_label.split(" ", 1)[1])
                          if (um and um.set_label) else None)
                m.add_member(mid, SNID + nid(i, s, ja), SNID + nid(i, s, jb),
                             stiff_name, member_set="upright stiffeners",
                             mesh=cfg.mesh_upright, vecxz=(0.0, 1.0, 0.0),
                             L_buckling_y=seg, L_buckling_z=seg,
                             area_factor=1.0, set_label=slabel)
                mid += 1
            zz = [zs[j] for j in zone_js]     # interface links at each node,
            for p, j in enumerate(zone_js):   # kz spread by tributary length
                lo = 0.5 * (zz[p] - zz[p - 1]) if p > 0 else 0.0
                hi = 0.5 * (zz[p + 1] - zz[p]) if p < len(zz) - 1 else 0.0
                # floor the tributary at half a bolt pitch so the end links keep
                # a realistic (>= ~half a bolt) stiffness and stay well-conditioned
                trib = max(lo + hi, 0.5 * cfg.stiffener_bolt_pitch)
                kz = (kz_fixed if kz_fixed is not None
                      else max(kz_per_mm * trib, 1.0))
                m.links.append(Link(node_i=nid(i, s, j),
                                    node_j=SNID + nid(i, s, j),
                                    kx=K_TRANS, ky=K_TRANS, kz=kz))
            # the reinforcement bears on the floor: vertical support at its base
            m.supports.append(Support(node=SNID + nid(i, s, 0), uz=True,
                                      ux=False, uy=False))

    # buckling is verified on the uprights (EN 15512); the stiffener members are
    # checked too.  Beams are checked for stress / moments / deflection.
    m.checks.buckling_sets = ["uprights"]
    if stiff_name:
        m.checks.buckling_sets.append("upright stiffeners")

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
        if cfg.master:
            n_modules = len(rack_pairs)
            total_pallets = sum(load for _, _, load in specs)
            N_est = (cfg.gamma_Q * total_pallets * cfg.n_bays
                     * n_modules) / n_uprights
            k_base, _ = cfg.master.base_stiffness(up.name, N_est)
        else:
            # no test data: keep the historical selective default
            k_base = 5.0e8
    elif cfg.base_stiffness == "derived":
        # calculated from the R899 formulas (floor + upright), h = first beam
        from .base_stiffness import derived_base_stiffness
        h0 = specs[0][0] if specs else (cfg.frame_height or 1200.0)
        k_base = derived_base_stiffness(up, m.materials[up.material].E, h0,
                                        f_ck=cfg.concrete_fck)
    else:
        k_base = float(cfg.base_stiffness)
    # The EN 15512 floor-connection test gives the DOWN-AISLE rotational
    # stiffness (bending in the X-Z plane -> M_y -> ry).  Cross-aisle (rx) is
    # provided by the braced frame, so the base is pinned about X.  Apply the
    # base spring in the down-aisle direction (ry) only.
    for i in range(n_lines):
        for s in sides:
            k = k_base if k_base > 0 else False
            m.supports.append(Support(nid(i, s, 0), ux=True, uy=True, uz=True,
                                      rx=False, ry=k, rz=False))
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

    # the frame (upright line) carrying the placement & accidental loads.
    # default (None) -> a governing INTERIOR line (shared between two bays);
    # an interior column carries ~twice the end-column axial, so the placement
    # and accidental impact land on the inner frame (RSTAB/EN 15512 practice),
    # not the corner/edge.  Single-bay runs have no interior line -> use line 0.
    if cfg.load_frame is None:
        li = cfg.n_bays // 2 if cfg.n_bays >= 2 else 0
    else:
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
        # EN 15512 / RSTAB CO2 & CO5: when the horizontal placement force acts
        # together with the pallet (live) load, BOTH are taken at the psi-reduced
        # factor pay_placement_factor (1.26 = 1.4 x 0.9), not the full gamma_Q.
        psi_pl = cfg.pay_placement_factor
        m.combinations.insert(1, Combination(
            "ULS2", "ULS", {"dead": cfg.gamma_G, "pallets": psi_pl,
                            "placement": psi_pl}))
        m.combinations.insert(2, Combination(
            "ULS3", "ULS", {"dead": cfg.gamma_G, "pallets": psi_pl,
                            "placement_y": psi_pl}))
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
    # looseness goes EITHER into the imperfection phi_l (default) OR is modelled
    # directly as a connector dead-band (model_connector_looseness) - never both
    phi_l_used = 0.0 if cfg.model_connector_looseness else max(looseness_used)
    m.imperfection = Imperfection(
        n_cols=n_lines, phi_s=cfg.phi_s, phi_s_cross=cfg.phi_s_cross,
        phi_l=phi_l_used, method=cfg.imperfection_method,
        standard=cfg.imperfection_standard,
        alpha_hm=cfg.imperfection_alpha_hm, height=H,
        directions=["+x", "-x", "+y", "-y"])
    m.base_axial_table = cfg.base_axial_table
    m.model_connector_looseness = cfg.model_connector_looseness
    m.analysis.stiffness_gamma_m = cfg.stiffness_gamma_m

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

    # the solver needs J > 0 on every section; an imported section may carry
    # J = 0 (sheet blank / rounded to zero) - fall back to the open thin-wall
    # estimate A*t^2/3 so the model validates and runs
    for sec in m.sections.values():
        if not sec.J or sec.J <= 0:
            sec.J = max(sec.A * (sec.t or 2.0) ** 2 / 3.0, 1.0)

    return m
