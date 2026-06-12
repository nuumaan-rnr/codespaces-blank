"""Data model for a 2D storage-rack frame (down-aisle or cross-aisle plane).

Units (consistent SI-mm set, used everywhere):
    length : mm
    force  : N
    moment : N*mm
    stress : MPa (N/mm^2)
    rotational spring stiffness : N*mm/rad
    distributed load : N/mm

Coordinate system: x horizontal, y vertical (gravity = -y).
Nodal DOFs: ux, uy, rz.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

# A support DOF is either fixed (True), free (False) or a spring stiffness
# (float > 0; N/mm for translations, N*mm/rad for rotation).
DofRestraint = Union[bool, float]


@dataclass
class Steel:
    """Steel material. fy is the design yield strength (for perforated rack
    uprights this is usually the average yield strength derived from tests
    per EN 15512 Annex A)."""

    name: str
    E: float = 210000.0       # MPa
    fy: float = 355.0         # MPa
    G: float = 81000.0        # MPa
    nu: float = 0.3


@dataclass
class CrossSection:
    """Cross-section properties about the in-plane bending axis.

    For cold-formed perforated uprights EN 15512 requires effective
    properties (A_eff, W_eff) obtained from stub-column / bending tests or
    EN 1993-1-3.  If not given they default to the gross values.
    """

    name: str
    material: str             # Steel name
    A: float                  # gross area, mm^2
    I: float                  # second moment of area, mm^4
    Wel: float                # elastic section modulus, mm^3
    A_eff: Optional[float] = None
    W_eff: Optional[float] = None
    buckling_curve: str = "b"  # EN 1993-1-1 Table 6.1: a0, a, b, c, d

    @property
    def area_eff(self) -> float:
        return self.A_eff if self.A_eff is not None else self.A

    @property
    def mod_eff(self) -> float:
        return self.W_eff if self.W_eff is not None else self.Wel

    @property
    def radius_of_gyration(self) -> float:
        return math.sqrt(self.I / self.A)


@dataclass
class Node:
    id: int
    x: float
    y: float


@dataclass
class Hinge:
    """Semi-rigid rotational connection at a member end (e.g. beam-to-upright
    connector).  Stiffness from EN 15512 Annex A bending tests.

    stiffness : rotational stiffness k [N*mm/rad]; 0.0 -> perfect pin.
    m_rd      : design moment resistance of the connector [N*mm] (checked
                against the analysis moment if given).
    looseness : connector looseness phi_l [rad].  Only used to compute the
                global sway imperfection; per EN 15512 it may be taken as 0
                in the imperfection if modelled in the connection itself.
    """

    stiffness: float
    m_rd: Optional[float] = None
    looseness: float = 0.0


@dataclass
class Member:
    """Beam or truss member between two nodes.

    mtype       : 'beam' (6 dof frame element) or 'truss' (axial only).
    hinge_i/j   : optional semi-rigid end connections (beams only).
    k_buckling  : effective length factor for in-plane flexural buckling.
                  With a full second-order analysis including imperfections
                  EN 15512 permits the system length (K = 1.0).
    L_buckling  : optional explicit buckling length [mm] (overrides K * L).
    mesh        : number of internal subdivisions (>= 1).  More segments give
                  better P-little-delta capture and deflected shapes.
    member_set  : group label used for check reporting (e.g. 'uprights',
                  'pallet beams', 'diagonals').
    """

    id: int
    node_i: int
    node_j: int
    section: str
    mtype: str = "beam"
    hinge_i: Optional[Hinge] = None
    hinge_j: Optional[Hinge] = None
    k_buckling: float = 1.0
    L_buckling: Optional[float] = None
    mesh: int = 2
    member_set: str = "default"


@dataclass
class Support:
    """Nodal support.  Each DOF: True = fixed, False = free, float = spring.

    A semi-rigid floor connection per EN 15512 is modelled with ux/uy fixed
    and rz = rotational stiffness from the floor-connection test.
    """

    node: int
    ux: DofRestraint = True
    uy: DofRestraint = True
    rz: DofRestraint = False


@dataclass
class NodalLoad:
    node: int
    fx: float = 0.0
    fy: float = 0.0
    mz: float = 0.0


@dataclass
class MemberLoad:
    """Uniformly distributed load on a member, in GLOBAL axes, per unit
    length of the member (qy = -w for gravity loads of magnitude w)."""

    member: int
    qx: float = 0.0
    qy: float = 0.0


@dataclass
class LoadCase:
    """case_type: 'permanent' (dead loads) | 'variable' (unit/pallet loads)
    | 'placement' (placement loads) | 'other'.  Only used for bookkeeping;
    combination factors are explicit."""

    name: str
    case_type: str = "variable"
    nodal_loads: List[NodalLoad] = field(default_factory=list)
    member_loads: List[MemberLoad] = field(default_factory=list)


@dataclass
class Imperfection:
    """Global sway imperfection per EN 15512.

    phi may be given directly.  Otherwise it is computed with the helper
    formula of EN 15512:2009 10.3.1 (verify against the edition you use):

        phi = sqrt(0.5 + 1/n_cols) * (2*phi_s + phi_l)   >= phi_min

    n_cols : number of interconnected uprights in the plane of bending.
    phi_s  : maximum specified out-of-plumb per unit height (erection
             tolerance, e.g. 1/350).
    phi_l  : connector looseness [rad]; 0 if modelled in the hinges.
    method : 'EHF' -> equivalent horizontal forces phi * V applied at every
             loaded node; 'geometry' -> initial out-of-plumb geometry
             (x' = x + phi * y).
    directions : imperfection senses to analyse; results are enveloped.
    """

    phi: Optional[float] = None
    n_cols: Optional[int] = None
    phi_s: float = 1.0 / 350.0
    phi_l: float = 0.0
    phi_min: float = 1.0 / 500.0
    method: str = "EHF"
    directions: List[int] = field(default_factory=lambda: [1, -1])

    def value(self) -> float:
        if self.phi is not None:
            return self.phi
        if not self.n_cols:
            raise ValueError(
                "Imperfection: give either phi directly or n_cols "
                "(+ phi_s, phi_l) to compute it.")
        phi = math.sqrt(0.5 + 1.0 / self.n_cols) * (2.0 * self.phi_s + self.phi_l)
        return max(phi, self.phi_min)


@dataclass
class Combination:
    """Load combination.  factors maps load-case name -> partial factor.

    EN 15512 defaults (verify against your edition / national annex):
      ULS:  1.3 * permanent + 1.4 * variable (unit loads)
      SLS:  1.0 * all
    Imperfections are applied to ULS combinations by default.
    """

    name: str
    kind: str                      # 'ULS' or 'SLS'
    factors: Dict[str, float]
    imperfection: bool = True


@dataclass
class AnalysisSettings:
    order: int = 2                 # 1 = linear, 2 = geometrically nonlinear
    n_steps: int = 10              # load increments for second order
    tolerance: float = 1.0e-6
    max_iter: int = 50


@dataclass
class CheckSettings:
    """EN 15512 / EN 1993 verification settings (all overridable)."""

    gamma_M0: float = 1.0          # cross-section resistance
    gamma_M1: float = 1.0          # member buckling resistance
    k_M: float = 1.0               # moment interaction factor in buckling check
    sway_limit_ratio: float = 200.0      # max sway <= H / ratio (SLS)
    beam_defl_limit_ratio: float = 200.0  # beam deflection <= L / ratio (SLS)
    alpha_cr_warn: float = 10.0    # below this, 2nd-order effects significant


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
    def add_node(self, nid: int, x: float, y: float) -> Node:
        n = Node(nid, x, y)
        self.nodes[nid] = n
        return n

    def add_member(self, mid: int, ni: int, nj: int, section: str, **kw) -> Member:
        m = Member(mid, ni, nj, section, **kw)
        self.members[mid] = m
        return m

    def member_length(self, m: Member) -> float:
        ni, nj = self.nodes[m.node_i], self.nodes[m.node_j]
        return math.hypot(nj.x - ni.x, nj.y - ni.y)

    def section_of(self, m: Member) -> CrossSection:
        return self.sections[m.section]

    def material_of(self, m: Member) -> Steel:
        return self.materials[self.sections[m.section].material]

    def height(self) -> float:
        ys = [n.y for n in self.nodes.values()]
        return max(ys) - min(ys)

    # ---- validation ------------------------------------------------------
    def validate(self) -> List[str]:
        errors: List[str] = []
        for s in self.sections.values():
            if s.material not in self.materials:
                errors.append(f"Section '{s.name}': unknown material '{s.material}'")
        for m in self.members.values():
            if m.node_i not in self.nodes or m.node_j not in self.nodes:
                errors.append(f"Member {m.id}: unknown node")
            if m.section not in self.sections:
                errors.append(f"Member {m.id}: unknown section '{m.section}'")
            if m.mtype not in ("beam", "truss"):
                errors.append(f"Member {m.id}: mtype must be 'beam' or 'truss'")
            if m.mtype == "truss" and (m.hinge_i or m.hinge_j):
                errors.append(f"Member {m.id}: truss members cannot have hinges")
            if m.node_i in self.nodes and m.node_j in self.nodes \
                    and self.member_length(m) < 1.0e-6:
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
        return errors
