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
