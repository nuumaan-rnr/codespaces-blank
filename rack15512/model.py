"""Data model for a 3D storage-rack structure.

Units (consistent SI-mm set, used everywhere):
    length : mm
    force  : N
    moment : N*mm
    stress : MPa (N/mm^2)
    rotational spring stiffness : N*mm/rad
    distributed load : N/mm

Global axes:  X = down-aisle, Y = cross-aisle (depth), Z = vertical (up).
Gravity acts in -Z.  Nodal DOFs: ux, uy, uz, rx, ry, rz.

Member local axes (right-handed, local x = node i -> node j):
  * non-vertical members: local y is vertical (up) -> gravity bending is
    about local z and engages Iz / Welz ("major" axis of pallet beams);
  * vertical members (uprights): local y = global +X (down-aisle), local
    z = global +Y -> down-aisle frame bending is about local z (Iz),
    cross-aisle bending about local y (Iy);
  * override per member with an explicit `vecxz` vector (defines the local
    x-z plane, OpenSees convention) when your section axes differ.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Union

# A support DOF is either fixed (True), free (False) or a spring stiffness
# (float > 0; N/mm for translations, N*mm/rad for rotations).
DofRestraint = Union[bool, float]


@dataclass
class Steel:
    """Steel material. fy is the design yield strength (for perforated rack
    uprights usually derived from tests per EN 15512 Annex A)."""

    name: str
    E: float = 210000.0       # MPa
    fy: float = 355.0         # MPa
    G: float = 81000.0        # MPa
    nu: float = 0.3


@dataclass
class CrossSection:
    """Full 3D cross-section properties (in member local axes, see module
    docstring).  Typically selected from the section master library.

    For cold-formed perforated uprights EN 15512 requires effective
    properties (A_eff, W_eff) from stub-column / bending tests or
    EN 1993-1-3; they default to the gross values when not given.
    role is a free label from the master ('upright', 'beam', 'bracing'...).
    """

    name: str
    material: str             # Steel name
    A: float                  # gross area, mm^2
    Iy: float                 # second moment about local y, mm^4
    Iz: float                 # second moment about local z, mm^4
    J: float                  # St-Venant torsion constant, mm^4
    Wely: float               # elastic modulus about local y, mm^3
    Welz: float               # elastic modulus about local z, mm^3
    A_eff: Optional[float] = None
    Wy_eff: Optional[float] = None
    Wz_eff: Optional[float] = None
    buckling_curve_y: str = "b"   # EN 1993-1-1 Table 6.1: a0, a, b, c, d
    buckling_curve_z: str = "b"
    role: str = ""
    description: str = ""
    # connection / detailing data from the master (used by the bolt-bearing
    # and base-plate checks; all optional)
    t: Optional[float] = None         # plate / wall thickness [mm]
    e1: Optional[float] = None        # edge distance in load direction [mm]
    e2: Optional[float] = None        # edge distance perpendicular [mm]
    fu: Optional[float] = None        # ultimate strength [MPa]
    width_b: Optional[float] = None   # overall section width [mm]
    depth_h: Optional[float] = None   # overall section depth [mm]
    # beam-to-upright connector data from the BEAM master (per beam type,
    # from EN 15512 Annex A tests); used automatically for the hinges of
    # every beam of this section
    connector_k: Optional[float] = None          # [N*mm/rad]
    connector_m_rd: Optional[float] = None        # [N*mm]
    connector_looseness: Optional[float] = None   # [rad]
    connector_v_rd: Optional[float] = None        # connector shear resist [N]
    connector_arm: float = 400.0                  # test cantilever arm a [mm]
    # beam-to-upright connector stiffness as a function of the UPRIGHT wall
    # thickness it bolts to: [[upl_mm, k N*mm/rad], ...] (from a beam-stiffness
    # import).  When present the builder resolves connector_k by the upright t.
    connector_k_by_upl: Optional[List[List[float]]] = None
    # gross-section torsion / warping properties for flexural-torsional
    # buckling (EN 15512 9.7.5); optional - FT buckling is included only
    # when present.  Iy_gross/Iz_gross default to Iy/Iz.
    It_gross: Optional[float] = None              # St-Venant torsion [mm^4]
    Iw_gross: Optional[float] = None              # warping constant [mm^6]
    y0: Optional[float] = None                    # shear-centre offset [mm]
    # for stiffener sections: cross-aisle distance from the UPRIGHT centroid line
    # to THIS stiffener's centroid line when mounted (the assembly centroid gap).
    # When given on the selected stiffener, the builder uses it to place the
    # stiffener node instead of the global RackConfig.stiffener_offset.
    mount_offset: Optional[float] = None          # [mm]
    Iy_gross: Optional[float] = None
    Iz_gross: Optional[float] = None
    # shear areas for Timoshenko (shear-flexible) beams [mm^2]; when both are
    # given the engine builds an ElasticTimoshenkoBeam so the deflection of
    # short, deep bays (e.g. drive-in rails) includes shear deformation, to
    # match RSTAB.  Left None -> Euler-Bernoulli elasticBeamColumn.
    Avy: Optional[float] = None                   # shear area along local y
    Avz: Optional[float] = None                   # shear area along local z

    @property
    def area_eff(self) -> float:
        return self.A_eff if self.A_eff is not None else self.A

    @property
    def mod_y_eff(self) -> float:
        return self.Wy_eff if self.Wy_eff is not None else self.Wely

    @property
    def mod_z_eff(self) -> float:
        return self.Wz_eff if self.Wz_eff is not None else self.Welz

    def connector_k_for(self, upright_t: Optional[float]) -> Optional[float]:
        """Beam-to-upright connector stiffness [N*mm/rad] for the upright wall
        thickness it bolts to: the closest UPL row of connector_k_by_upl when
        present (and a thickness is known), else the single connector_k."""
        tbl = self.connector_k_by_upl
        if tbl and upright_t:
            row = min(tbl, key=lambda r: abs(r[0] - upright_t))
            return row[1]
        if tbl:
            # no upright thickness known: use the middle UPL row
            return sorted(tbl, key=lambda r: r[0])[len(tbl) // 2][1]
        return self.connector_k

    @property
    def iy(self) -> float:
        return math.sqrt(self.Iy / self.A)

    @property
    def iz(self) -> float:
        return math.sqrt(self.Iz / self.A)


@dataclass
class Node:
    id: int
    x: float
    y: float
    z: float


@dataclass
class Hinge:
    """Semi-rigid / released rotational connection at a member end (e.g.
    beam-to-upright connector).  Per local rotation axis:

        None  -> continuous (rigid connection for that axis)
        0.0   -> released (perfect pin about that axis)
        > 0   -> spring stiffness [N*mm/rad]

    rz governs gravity bending of horizontal beams (the EN 15512 Annex A
    connector test stiffness goes here); ry the out-of-plane bending; rx
    torsion.  Translations are always continuous.

    m_rd_z / m_rd_y : design moment resistance of the connector about the
                      corresponding axis [N*mm] (checked when given).
    looseness       : connector looseness phi_l [rad], used only in the
                      global sway imperfection (may be 0 if modelled here).
    """

    rz: Optional[float] = None
    ry: Optional[float] = None
    rx: Optional[float] = None
    m_rd_z: Optional[float] = None
    m_rd_y: Optional[float] = None
    looseness: float = 0.0
    # optional NONLINEAR moment-rotation diagram for the connector (rz) axis:
    # [[phi_rad, M_Nmm], ...] for phi >= 0 (the engine mirrors it for -phi).
    # When given, the engine builds a multilinear M-phi connector (semi-rigid
    # hinge nonlinearity, RSTAB-style) instead of the linear rz spring.
    m_phi_z: Optional[List[List[float]]] = None
    # plastic (Hysteretic) connector law about rz: elastic at rz up to m_rd_z,
    # then hardening (ratio b) to phi_u - for pushover / loading past the
    # connection moment capacity.  Used when plastic=True and m_rd_z is given.
    plastic: bool = False
    hardening: float = 0.02       # post-yield stiffness ratio b
    phi_u: float = 0.05           # rotation at the ultimate point [rad]


@dataclass
class Member:
    """Beam or truss member between two nodes.

    mtype          : 'beam' (12 dof frame element) or 'truss' (axial only).
    hinge_i/j      : optional end connections (beams only).
    vecxz          : optional (x, y, z) vector defining the local x-z plane
                     (OpenSees convention); default per module docstring.
    k_buckling_y/z : effective length factors for flexural buckling about
                     the local y / z axes.  With second-order global
                     analysis + imperfections EN 15512 permits the system
                     length (K = 1.0).
    L_buckling_y/z : explicit buckling lengths [mm] (override K * L).
    mesh           : internal subdivisions (>= 1) for P-little-delta and
                     deflected shapes.
    member_set     : group label for reporting ('uprights', 'pallet beams',
                     'bracing', ...).
    set_label      : RSTAB-style continuous-member-set name for an upright
                     storey segment (e.g. 'Upright A1 . base->L1'); the set
                     length is the down-aisle buckling length Lcr,DA.  Used to
                     group/report upright buckling per set.  None for members
                     that are not part of a named set.
    area_factor    : stiffness modification on the section area used in the
                     ANALYSIS only (e.g. 0.15 on bracing to represent the
                     flexibility of the bolted end connections); strength
                     checks use the full section.
    """

    id: int
    node_i: int
    node_j: int
    section: str
    mtype: str = "beam"
    hinge_i: Optional[Hinge] = None
    hinge_j: Optional[Hinge] = None
    vecxz: Optional[Tuple[float, float, float]] = None
    k_buckling_y: float = 1.0
    k_buckling_z: float = 1.0
    L_buckling_y: Optional[float] = None
    L_buckling_z: Optional[float] = None
    mesh: int = 2
    member_set: str = "default"
    area_factor: float = 1.0
    set_label: Optional[str] = None


@dataclass
class Support:
    """Nodal support.  Each DOF: True = fixed, False = free, float = spring.

    A semi-rigid floor connection per EN 15512: ux/uy/uz fixed, rx/ry =
    rotational stiffness from the floor-connection test (rx resists
    cross-aisle rocking, ry resists down-aisle sway)."""

    node: int
    ux: DofRestraint = True
    uy: DofRestraint = True
    uz: DofRestraint = True
    rx: DofRestraint = False
    ry: DofRestraint = False
    rz: DofRestraint = False

    def restraints(self) -> Tuple[DofRestraint, ...]:
        return (self.ux, self.uy, self.uz, self.rx, self.ry, self.rz)


@dataclass
class NodalLoad:
    node: int
    fx: float = 0.0
    fy: float = 0.0
    fz: float = 0.0
    mx: float = 0.0
    my: float = 0.0
    mz: float = 0.0


@dataclass
class MemberLoad:
    """Uniformly distributed load on a member, in GLOBAL axes, per unit
    length of the member (qz = -w for a gravity load of magnitude w)."""

    member: int
    qx: float = 0.0
    qy: float = 0.0
    qz: float = 0.0


@dataclass
class LoadCase:
    """case_type: 'permanent' | 'variable' | 'placement' | 'other' -
    bookkeeping only; combination factors are explicit."""

    name: str
    case_type: str = "variable"
    nodal_loads: List[NodalLoad] = field(default_factory=list)
    member_loads: List[MemberLoad] = field(default_factory=list)


@dataclass
class Imperfection:
    """Global sway imperfection per EN 15512.

    phi may be given directly; otherwise computed with the helper formula
    of EN 15512:2009 10.3.1 (verify against the edition you use):

        phi = sqrt(0.5 + 1/n_cols) * (2*phi_s + phi_l)   >= phi_min

    method     : 'EHF' (equivalent horizontal forces phi * V at every
                 loaded node) or 'geometry' (initial out-of-plumb).
    directions : sway senses analysed and enveloped; any of
                 '+x', '-x' (down-aisle), '+y', '-y' (cross-aisle).
    """

    phi: Optional[float] = None
    n_cols: Optional[int] = None
    phi_s: float = 1.0 / 350.0
    phi_s_cross: Optional[float] = None     # cross-aisle (+y/-y) out-of-plumb;
    #                                         None -> use phi_s in both directions
    phi_l: float = 0.0
    phi_min: float = 1.0 / 500.0
    method: str = "EHF"
    # 'EN15512' -> phi = sqrt(0.5+1/n)*(2*phi_s+phi_l) (the amplified rack value);
    # 'EN1993'  -> phi = phi_s directly (the plain out-of-plumb, e.g. 1/300), as a
    #              generic frame / RSTAB-style imperfection (no 2x or sqrt factor).
    standard: str = "EN15512"
    # EN 1993-1-1 5.3.2(3) reduction factors phi = phi_s * alpha_h * alpha_m,
    # with alpha_h = 2/sqrt(h) (clamped 2/3..1.0, h in metres) and
    # alpha_m = sqrt(0.5*(1+1/m)).  Only applied when standard == 'EN1993' and
    # alpha_hm is True (RSTAB's "Calculate value of inclination" dialog); the
    # phi_min floor is then NOT applied, matching RSTAB.  height is in mm; m is
    # the number of columns in a row (n_cols).
    alpha_hm: bool = False
    height: Optional[float] = None          # structure height h [mm] for alpha_h
    directions: List[str] = field(
        default_factory=lambda: ["+x", "-x", "+y", "-y"])

    def _alpha_hm(self) -> float:
        h_m = (self.height or 0.0) / 1000.0
        a_h = max(2.0 / 3.0, min(1.0, 2.0 / math.sqrt(h_m))) if h_m > 0 else 1.0
        m = self.n_cols or 1
        a_m = math.sqrt(0.5 * (1.0 + 1.0 / m)) if m >= 1 else 1.0
        return a_h * a_m

    def _phi_from(self, phi_s: float) -> float:
        if self.phi is not None:
            return self.phi
        if self.standard.upper() == "EN1993":
            if self.alpha_hm:                       # EN 1993-1-1 5.3.2(3)
                return phi_s * self._alpha_hm()     # no phi_min floor (RSTAB)
            return max(phi_s, self.phi_min if self.phi_min < phi_s else 0.0)
        if not self.n_cols:
            raise ValueError(
                "Imperfection: give either phi directly or n_cols "
                "(+ phi_s, phi_l) to compute it.")
        phi = math.sqrt(0.5 + 1.0 / self.n_cols) * (2.0 * phi_s + self.phi_l)
        return max(phi, self.phi_min)

    def value(self) -> float:
        """Down-aisle (X) imperfection (also the default for all directions)."""
        return self._phi_from(self.phi_s)

    def value_for(self, direction: str) -> float:
        """Direction-specific imperfection: cross-aisle (+y/-y) uses
        phi_s_cross when given (EN 15512 / RSTAB use a larger cross-aisle
        out-of-plumb), otherwise the down-aisle value."""
        if direction in ("+y", "-y") and self.phi_s_cross is not None:
            return self._phi_from(self.phi_s_cross)
        return self._phi_from(self.phi_s)


DIRECTION_VECTORS: Dict[str, Tuple[float, float]] = {
    "+x": (1.0, 0.0), "-x": (-1.0, 0.0),
    "+y": (0.0, 1.0), "-y": (0.0, -1.0),
}


@dataclass
class Combination:
    """Load combination; factors maps load-case name -> partial factor.

    EN 15512 defaults (verify for your edition / national annex):
      ULS:  1.3 * permanent + 1.4 * variable (unit loads)
      SLS:  1.0 * all
    Imperfections are applied to ULS combinations by default.
    imp_directions overrides the model-level imperfection directions for
    this combination (e.g. ['+x'] when the combination represents one
    specific sway sense)."""

    name: str
    kind: str                      # 'ULS' or 'SLS'
    factors: Dict[str, float]
    imperfection: bool = True
    imp_directions: Optional[List[str]] = None


@dataclass
class AnalysisSettings:
    order: int = 2                 # 1 = linear, 2 = geometrically nonlinear
    n_steps: int = 5               # load increments for second order; the engine
    #                                auto-retries at 5x on non-convergence, so a
    #                                low value is fast yet robust (same equilibrium)
    tolerance: float = 1.0e-5      # NormDispIncr [mm]; tighter values can
    #                                stall on penalty-spring round-off
    max_iter: int = 50
    # run the extra first-order companion solve per case for the ALPHA_CR
    # sway-sensitivity report; set False to skip it and roughly halve the
    # number of solves (the ALPHA_CR informative check is then omitted)
    compute_alpha_cr: bool = True
    # fast/lean solve: a single accelerated KrylovNewton attempt at the given
    # n_steps/max_iter instead of the full robust cascade (Newton ->
    # KrylovNewton x1/x4 -> NewtonLineSearch x10).  Used by load-chart sweeps,
    # where non-convergence simply means "load too high" and must be detected
    # cheaply (the production default keeps the full cascade for accuracy).
    fast_solve: bool = False


@dataclass
class SeismicSettings:
    """IS 1893:2016 seismic (modal response spectrum) settings.

    Ah = (Z/2)*(I/R)*(Sa/g); the design spectrum Sa/g (5% damping) follows
    Cl 6.4.2 by soil type.  Seismic mass = dead + imposed_factor*pallets
    (IS 1893 Table 8).  Modes are auto-increased to capture >= 90% mass per
    direction (Cl 7.7.5.2); responses combined by SRSS/CQC, base-shear scaled
    to the empirical-period static value (Cl 7.7.3), directions combined
    100%+30% (Cl 6.3.4.1).
    """

    enabled: bool = False
    zone: str = "III"              # 'II'|'III'|'IV'|'V' -> Z 0.10/0.16/0.24/0.36
    importance: float = 1.0        # I (Table 8); 1.5 for important
    response_reduction: float = 4.0  # R (Table 9); braced ~4, OMRF ~3, SMRF ~5
    structure_type: str = "Storage rack - cross-aisle braced"  # informs R
    soil_type: str = "II"          # 'I' rock | 'II' medium | 'III' soft
    damping: float = 0.05          # for CQC
    imposed_factor: float = 0.8    # kappa: pallet (live) load share in W (DL+0.8LL)
    n_modes: int = 6               # initial/min eigen request
    max_modes: int = 12            # cap when auto-increasing for 90% mass
    combination: str = "SRSS"      # 'SRSS' | 'CQC'
    include_self_mass: bool = True  # add member A*L*rho to the lumped mass
    apply_base_shear_scaling: bool = True   # Cl 7.7.3
    # storey-drift limit ratio Δ/h.  Racks have no brittle non-structural
    # attachments, so EN 1998-1 §4.4.3.2 / EN 16681 §8.5 permit larger drifts
    # than the IS 1893 Cl 7.11.1 building value (0.004): 0.005 brittle, 0.0075
    # ductile, 0.010 none (racks).  Default to the rack value; overridable.
    drift_limit_ratio: float = 0.010
    theta_limit: float = 0.10               # P-Δ negligible threshold (EN 4.4.2)
    theta_max: float = 0.30                 # P-Δ not permitted (EN 1998-1 4.4.2.2)
    # EN 16681 unit-load sliding: the pallet-to-beam friction caps the horizontal
    # seismic force a pallet can transfer at ~ c_mu_h*mu*W_pallet.  When enabled,
    # the pallet (live) mass lateral force is reduced accordingly; structure dead
    # mass is never capped.  pallet_mu is the design friction coefficient.
    pallet_sliding: bool = False
    pallet_mu: float = 0.37                  # wood-on-steel typical (verify)
    c_mu_h: float = 1.5                      # EN 16681 amplification on friction
    # IS 800 LSD seismic combination rows: (label, f_dead, f_imposed, f_seismic)
    combos: Tuple[Tuple[str, float, float, float], ...] = (
        ("1.2(DL+IL+EL)", 1.2, 1.2, 1.2),
        ("1.5(DL+EL)", 1.5, 0.0, 1.5),
        ("0.9DL+1.5EL", 0.9, 0.0, 1.5),
    )


@dataclass
class CheckSettings:
    """EN 15512 / EN 1993 verification settings (all overridable)."""

    gamma_M0: float = 1.0          # cross-section resistance (EN 15512: 1.0)
    gamma_M1: float = 1.1          # member buckling/stability resistance (EN 15512: 1.1)
    k_M: float = 1.0               # moment interaction factor (buckling)
    # pallet beams are normally laterally restrained by the unit load; when True
    # the LTB check records that assumption (informative) instead of computing
    # chi_LT (EN 15512 9.4)
    beam_laterally_restrained: bool = True
    # upright splice connection verification: off by default (the upright is
    # still checked as a continuous member); the splice geometry only appears
    # for very tall frames (cfg.splice_above)
    check_splice: bool = False
    sway_limit_ratio: float = 200.0       # max sway <= H / ratio (SLS)
    beam_defl_limit_ratio: float = 200.0  # beam deflection <= L / ratio (SLS)
    alpha_cr_warn: float = 10.0
    # torsional buckling length factor beta_T (EN 15512 9.7.5.2 / fig 24):
    # 1.0 with full torsional restraint at bracing, 0.7 with the typical
    # bolted brace connection; applied to the member torsional length
    beta_T: float = 0.7
    # member sets to verify for flexural buckling.  Per EN 15512 practice
    # buckling is checked on the uprights (columns) only; beams are checked
    # for stress / moments / deflection.  None = automatic: member sets
    # named 'uprights' or whose section role is 'upright'; if none exist,
    # all compressed members are checked (generic-model fallback).
    buckling_sets: Optional[List[str]] = None
    # bracing bolt-connection check (EN 1993-1-8): set bolt_d to enable.
    # Resistance = bolts_per_connection x min(bolt shear, bearing on the
    # brace, bearing on the upright), with bearing from d, t, e1, e2, fu of
    # each connected ply (e1/e2/t/fu from the section master).
    bolt_d: Optional[float] = None           # bolt diameter [mm], e.g. 12
    bolt_grade: str = "4.6"                  # 4.6/4.8/5.6/5.8/6.8/8.8/10.9
    bolts_per_connection: int = 1
    brace_planes: int = 1          # shear planes of the brace bolt (1 single C,
    #                                2 double / back-to-back C) -> bolt shear
    gamma_M2: float = 1.25
    # fallback ultimate strength when a section has no fu in the master
    fu_over_fy: float = 1.10


@dataclass
class BasePlate:
    """Footplate (base plate) check inputs per EN 15512 9.9 / 9.10 (contact
    pressure on the floor and base plate, strip method).

    Floor design strength fj = 2.5 * f_ck / gamma_c (EN 15512 9.10.1); the
    bearing stress under the upright wall spreads over a strip of half-width
    e = t * sqrt(fy / (3 fj)) (capped at the plate overhang), giving the
    effective contact area Abas.  The base partial-restraint moment is a
    SEPARATE check (m_rd_n table from the floor-connection tests).
    """

    f_ck: float = 25.0                 # concrete grade [MPa]
    gamma_c: float = 1.5
    f_jd: Optional[float] = None       # direct override [MPa]
    fy_plate: float = 250.0            # plate steel [MPa]
    b: Optional[float] = None          # actual plate width (X) [mm]
    d: Optional[float] = None          # actual plate depth (Y) [mm]
    t: Optional[float] = None          # actual plate thickness [mm]
    # load-dependent base moment resistance MRd(N) from the floor-connection
    # tests (EN 15512 9.4.4.3 / BASE_STIFFNESS sheet): [(N [N], M_Rd [N*mm])]
    m_rd_n: Optional[List[Tuple[float, float]]] = None
    # overturning / anchorage (EN 15512 7.6, 9.10.4): EN 15512 minimum that
    # every upright-floor connection must always provide
    anchor_tension: float = 3000.0     # min connection tension [N]
    anchor_shear: float = 5000.0       # min connection shear [N]
    # ---- Profis-Hilti-style wedge-anchor design (EN 1992-4, non-seismic) ----
    n_anchors: int = 2                 # anchors per footplate
    anchor_d: float = 12.0             # anchor diameter [mm] (M12 default)
    anchor_grade: str = "5.6"          # anchor steel grade
    anchor_hef: float = 70.0           # effective embedment [mm]
    anchor_spacing: Optional[float] = None   # lever between anchors [mm]
    anchor_edge: Optional[float] = None      # edge distance [mm]; None = no edge
    anchor_pullout_rk: Optional[float] = None  # N_Rk,p [N]; None = default table
    anchor_shear_rk: Optional[float] = None    # V_Rk,c [N]; None = default table
    gamma_ms_n: Optional[float] = None  # steel tension factor; None = from grade
    gamma_ms_v: Optional[float] = None  # steel shear factor; None = from grade
    gamma_mc: float = 1.5               # concrete (pull-out / cone / edge)

    def bearing_strength(self) -> float:
        """Floor design bearing strength fj [MPa] (EN 15512 9.10.1)."""
        return self.f_jd if self.f_jd is not None \
            else 2.5 * self.f_ck / self.gamma_c

    def m_rd_at(self, N: float) -> Optional[float]:
        """Base moment resistance at axial load N [N], interpolated."""
        tbl = self.m_rd_n
        if not tbl:
            return None
        if N <= tbl[0][0]:
            return tbl[0][1]
        if N >= tbl[-1][0]:
            return tbl[-1][1]
        for (n0, m0), (n1, m1) in zip(tbl, tbl[1:]):
            if n0 <= N <= n1:
                return m0 + (m1 - m0) * (N - n0) / (n1 - n0)
        return tbl[-1][1]


@dataclass
class Splice:
    """Upright splice at elevation z (required when the upright is longer
    than the maximum manufacturable length, typically > 11000 mm).

    The bolt group on EACH side of the splice has `rows` bolts along the
    upright axis at pitch p1 and `cols` bolt columns across at pitch p2,
    with end/edge distances e1 (along) and e2 (across).  The connection is
    verified per EN 1993-1-8 with the elastic bolt-group method for the
    concurrent N, V and M at the splice elevation; bearing is checked on
    the lesser of the upright wall and the sleeve thickness `t_sleeve`
    (default: equal to the upright wall)."""

    z: float
    bolt_d: float = 12.0
    bolt_grade: str = "4.6"
    rows: int = 2                  # bolts along the upright axis (pitch p1)
    cols: int = 1                  # bolt columns across (pitch p2)
    e1: float = 30.0               # end distance along the axis [mm]
    e2: float = 20.0               # edge distance across [mm]
    p1: float = 60.0               # pitch along [mm]
    p2: float = 0.0                # pitch across [mm] (cols > 1)
    t_sleeve: Optional[float] = None


@dataclass
class Link:
    """Interface connection between two (offset) nodes via translational springs
    in the GLOBAL axes (rotations free).  Models the upright<->stiffener bolt
    interface: stiff transverse (kx, ky) so the two members deflect together and
    share bending, and a finite vertical bolt-shear stiffness (kz) so the axial
    transfers by shear flow (partial composite, not a forced 50% split)."""

    node_i: int
    node_j: int
    kx: float
    ky: float
    kz: float


@dataclass
class BuiltUpColumn:
    """Built-up (battened or laced) end / anchor column per EN 1993-1-1 6.4.

    Two parallel chords (the standard upright section, unless `chord_section`
    names another) at centroid spacing `h0`, connected by battens (plates) or
    lacing (diagonals).  The BUILT_UP check amplifies the column's first-order
    moment for the built-up bow + reduced shear stiffness and verifies the most
    loaded chord over a panel length.

    Geometry that is product-specific (chord spacing, panel/batten spacing,
    lacing diagonal) is exposed here with conservative defaults flagged
    "confirm" — set them from the actual boxed-frame detail.

    target_set : member set whose members are treated as built-up columns
                 (the drive-in builder tags the reinforced end uprights).
    """

    target_set: str = "end columns"
    arrangement: str = "battened"      # "battened" | "laced"
    n_chords: int = 2
    chord_section: Optional[str] = None  # None -> use each member's own section
    h0: float = 100.0                  # chord centroid spacing [mm] (confirm)
    panel_a: float = 500.0             # batten / lacing panel spacing a [mm]
    L: Optional[float] = None          # column length [mm]; None -> member length
    e0_ratio: float = 500.0            # initial bow imperfection e0 = L / ratio
    gamma_M1: float = 1.1              # member buckling/stability resistance (EN 15512: 1.1)
    # battened: stiffness of one batten about the column axis (I_b) [mm^4];
    # large value -> the chord term governs S_v (EN 1993-1-1 eq 6.73)
    batten_I: Optional[float] = None
    n_planes: int = 2                  # batten / lacing planes (faces)
    # laced: single diagonal area A_d [mm^2] and diagonal length d [mm]; when
    # d is None it is taken as sqrt(h0^2 + panel_a^2)
    lacing_area: Optional[float] = None
    lacing_d: Optional[float] = None
    lacing_n_per_panel: int = 2        # diagonals per panel per plane


@dataclass
class RackModel:
    name: str = "rack"
    materials: Dict[str, Steel] = field(default_factory=dict)
    sections: Dict[str, CrossSection] = field(default_factory=dict)
    nodes: Dict[int, Node] = field(default_factory=dict)
    members: Dict[int, Member] = field(default_factory=dict)
    supports: List[Support] = field(default_factory=list)
    load_cases: Dict[str, LoadCase] = field(default_factory=dict)
    combinations: List[Combination] = field(default_factory=list)
    imperfection: Imperfection = field(default_factory=Imperfection)
    analysis: AnalysisSettings = field(default_factory=AnalysisSettings)
    checks: CheckSettings = field(default_factory=CheckSettings)
    seismic: Optional[SeismicSettings] = None
    seismic_summary: Optional[dict] = None     # filled by run_seismic for reports
    base_plate: Optional[BasePlate] = None
    splices: List[Splice] = field(default_factory=list)
    links: List[Link] = field(default_factory=list)
    built_up: Optional[BuiltUpColumn] = None
    # drive-in: how the down-aisle base rotational stiffness was obtained
    # ('master tested table' / 'calculated (R899)' / 'explicit') and its value
    # [N*mm/rad], for the report; set by the drive-in builder.
    base_stiffness_source: str = ""
    base_stiffness_value: float = 0.0
    # nonlinear axial-dependent base: [[P_kN, C_Nmm_per_rad], ...] - the base
    # rotational stiffness (about the down-aisle bending axis, support.ry) as a
    # function of column compression; 0 at uplift (tearing).  When set, the engine
    # iterates the base spring (fixed-point on the support reactions) per case.
    base_axial_table: Optional[List[List[float]]] = None
    # when True the engine models connector looseness (hinge.looseness) as a
    # rotational dead-band; otherwise the hinge value is only a record and the
    # looseness is carried in the sway imperfection phi_l (the default).
    model_connector_looseness: bool = False

    # ---- convenience builders -------------------------------------------
    def add_node(self, nid: int, x: float, y: float, z: float) -> Node:
        n = Node(nid, x, y, z)
        self.nodes[nid] = n
        return n

    def add_member(self, mid: int, ni: int, nj: int, section: str, **kw) -> Member:
        m = Member(mid, ni, nj, section, **kw)
        self.members[mid] = m
        return m

    def member_length(self, m: Member) -> float:
        ni, nj = self.nodes[m.node_i], self.nodes[m.node_j]
        return math.sqrt((nj.x - ni.x) ** 2 + (nj.y - ni.y) ** 2
                         + (nj.z - ni.z) ** 2)

    def member_axes(self, m: Member) -> Tuple[Tuple[float, float, float],
                                              Tuple[float, float, float],
                                              Tuple[float, float, float]]:
        """Local axes (x_hat, y_hat, z_hat) per the documented convention."""
        ni, nj = self.nodes[m.node_i], self.nodes[m.node_j]
        L = self.member_length(m)
        xh = ((nj.x - ni.x) / L, (nj.y - ni.y) / L, (nj.z - ni.z) / L)
        if m.vecxz is not None:
            v = m.vecxz
        elif abs(xh[2]) > 0.999:               # vertical member
            v = (0.0, 1.0, 0.0)
        else:                                   # local y as vertical as possible
            v = _cross(xh, (0.0, 0.0, 1.0))    # vecxz = x_hat x Z
        yh = _normalize(_cross(v, xh))         # OpenSees: y = vecxz x x_hat
        zh = _cross(xh, yh)
        return xh, yh, zh

    def member_vecxz(self, m: Member) -> Tuple[float, float, float]:
        xh, yh, zh = self.member_axes(m)
        return zh                               # z_hat lies in the x-z plane

    def section_of(self, m: Member) -> CrossSection:
        return self.sections[m.section]

    def material_of(self, m: Member) -> Steel:
        return self.materials[self.sections[m.section].material]

    def height(self) -> float:
        zs = [n.z for n in self.nodes.values()]
        return max(zs) - min(zs)

    # ---- validation ------------------------------------------------------
    def validate(self) -> List[str]:
        errors: List[str] = []
        for s in self.sections.values():
            if s.material not in self.materials:
                errors.append(f"Section '{s.name}': unknown material '{s.material}'")
            if s.J <= 0:
                errors.append(f"Section '{s.name}': torsion constant J must be > 0")
        for m in self.members.values():
            if m.node_i not in self.nodes or m.node_j not in self.nodes:
                errors.append(f"Member {m.id}: unknown node")
                continue
            if m.section not in self.sections:
                errors.append(f"Member {m.id}: unknown section '{m.section}'")
            if m.mtype not in ("beam", "truss"):
                errors.append(f"Member {m.id}: mtype must be 'beam' or 'truss'")
            if m.mtype == "truss" and (m.hinge_i or m.hinge_j):
                errors.append(f"Member {m.id}: truss members cannot have hinges")
            if self.member_length(m) < 1.0e-6:
                errors.append(f"Member {m.id}: zero length")
        for lk in self.links:
            if lk.node_i not in self.nodes or lk.node_j not in self.nodes:
                errors.append(f"Link {lk.node_i}-{lk.node_j}: unknown node")
        sup_nodes = set()
        for s in self.supports:
            if s.node not in self.nodes:
                errors.append(f"Support at unknown node {s.node}")
            sup_nodes.add(s.node)
        if not sup_nodes:
            errors.append("Model has no supports")
        for lc in self.load_cases.values():
            for nl in lc.nodal_loads:
                if nl.node not in self.nodes:
                    errors.append(f"Load case '{lc.name}': unknown node {nl.node}")
            for ml in lc.member_loads:
                if ml.member not in self.members:
                    errors.append(f"Load case '{lc.name}': unknown member {ml.member}")
        for c in self.combinations:
            if c.kind not in ("ULS", "SLS", "SEISMIC"):
                errors.append(f"Combination '{c.name}': kind must be ULS, SLS "
                              "or SEISMIC")
            for case in c.factors:
                if case not in self.load_cases:
                    errors.append(f"Combination '{c.name}': unknown case '{case}'")
            for d in c.imp_directions or []:
                if d not in DIRECTION_VECTORS:
                    errors.append(f"Combination '{c.name}': bad imperfection "
                                  f"direction '{d}'")
        for d in self.imperfection.directions:
            if d not in DIRECTION_VECTORS:
                errors.append(f"Imperfection direction '{d}' not in "
                              f"{sorted(DIRECTION_VECTORS)}")
        return errors


def _cross(a, b) -> Tuple[float, float, float]:
    return (a[1] * b[2] - a[2] * b[1],
            a[2] * b[0] - a[0] * b[2],
            a[0] * b[1] - a[1] * b[0])


def _normalize(a) -> Tuple[float, float, float]:
    n = math.sqrt(a[0] ** 2 + a[1] ** 2 + a[2] ** 2)
    if n < 1.0e-12:
        raise ValueError("member vecxz is parallel to the member axis")
    return (a[0] / n, a[1] / n, a[2] / n)
