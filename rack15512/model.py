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
    connector_m_rd: Optional[float] = None       # [N*mm]
    connector_looseness: Optional[float] = None  # [rad]

    @property
    def area_eff(self) -> float:
        return self.A_eff if self.A_eff is not None else self.A

    @property
    def mod_y_eff(self) -> float:
        return self.Wy_eff if self.Wy_eff is not None else self.Wely

    @property
    def mod_z_eff(self) -> float:
        return self.Wz_eff if self.Wz_eff is not None else self.Welz

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
    phi_l: float = 0.0
    phi_min: float = 1.0 / 500.0
    method: str = "EHF"
    directions: List[str] = field(
        default_factory=lambda: ["+x", "-x", "+y", "-y"])

    def value(self) -> float:
        if self.phi is not None:
            return self.phi
        if not self.n_cols:
            raise ValueError(
                "Imperfection: give either phi directly or n_cols "
                "(+ phi_s, phi_l) to compute it.")
        phi = math.sqrt(0.5 + 1.0 / self.n_cols) * (2.0 * self.phi_s + self.phi_l)
        return max(phi, self.phi_min)


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
    n_steps: int = 10              # load increments for second order
    tolerance: float = 1.0e-5      # NormDispIncr [mm]; tighter values can
    #                                stall on penalty-spring round-off
    max_iter: int = 50


@dataclass
class CheckSettings:
    """EN 15512 / EN 1993 verification settings (all overridable)."""

    gamma_M0: float = 1.0          # cross-section resistance
    gamma_M1: float = 1.0          # member buckling resistance
    k_M: float = 1.0               # moment interaction factor (buckling)
    sway_limit_ratio: float = 200.0       # max sway <= H / ratio (SLS)
    beam_defl_limit_ratio: float = 200.0  # beam deflection <= L / ratio (SLS)
    alpha_cr_warn: float = 10.0
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
    gamma_M2: float = 1.25
    # fallback ultimate strength when a section has no fu in the master
    fu_over_fy: float = 1.10


@dataclass
class BasePlate:
    """Footplate (base plate) check inputs per EN 1993-1-8 6.2.5 (rigid
    plate, cantilever-projection method).

    f_jd = design bearing strength of the floor joint; if not given it is
    taken as alpha_cc * f_ck / gamma_c.  When the actual plate b x d x t is
    given the check verifies it; the report always states the minimum
    required plate size and thickness for the governing base reaction.
    """

    f_ck: float = 25.0                 # concrete grade [MPa]
    gamma_c: float = 1.5
    alpha_cc: float = 0.85
    f_jd: Optional[float] = None       # direct override [MPa]
    fy_plate: float = 250.0            # plate steel [MPa]
    b: Optional[float] = None          # actual plate width (X) [mm]
    d: Optional[float] = None          # actual plate depth (Y) [mm]
    t: Optional[float] = None          # actual plate thickness [mm]

    def bearing_strength(self) -> float:
        return self.f_jd if self.f_jd is not None \
            else self.alpha_cc * self.f_ck / self.gamma_c


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
    base_plate: Optional[BasePlate] = None
    splices: List[Splice] = field(default_factory=list)

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
            if c.kind not in ("ULS", "SLS"):
                errors.append(f"Combination '{c.name}': kind must be ULS or SLS")
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
