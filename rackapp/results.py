"""Engine-neutral result containers (3D)."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeResult:
    ux: float = 0.0     # m, down-aisle
    uy: float = 0.0     # m, cross-aisle
    uz: float = 0.0     # m, vertical
    rx: float = 0.0     # rad
    ry: float = 0.0     # rad
    rz: float = 0.0     # rad


@dataclass
class MemberResult:
    """End forces in local member axes (internal-force sign convention).

    N: axial (tension positive); Vy/Vz: shear in local y/z;
    Mt: torsion; My: bending about local y (major / vertical-plane for beams,
    down-aisle for uprights); Mz: bending about local z (cross-aisle for
    uprights, horizontal-plane for beams).
    My_span_max: max |My| along the member (incl. span loading).
    defl_rel_max: max local-z deflection relative to the chord between the
    member ends (the quantity checked against L/200).
    """
    N1: float = 0.0
    Vy1: float = 0.0
    Vz1: float = 0.0
    Mt1: float = 0.0
    My1: float = 0.0
    Mz1: float = 0.0
    N2: float = 0.0
    Vy2: float = 0.0
    Vz2: float = 0.0
    Mt2: float = 0.0
    My2: float = 0.0
    Mz2: float = 0.0
    My_span_max: float = 0.0
    defl_rel_max: float = 0.0

    @property
    def N_max_compression(self) -> float:
        """Largest compressive axial force as a positive number."""
        return max(0.0, -min(self.N1, self.N2))

    @property
    def My_abs_max(self) -> float:
        return max(abs(self.My1), abs(self.My2), abs(self.My_span_max))

    @property
    def Mz_abs_max(self) -> float:
        return max(abs(self.Mz1), abs(self.Mz2))


@dataclass
class Reaction:
    fx: float = 0.0     # N
    fy: float = 0.0     # N
    fz: float = 0.0     # N
    mx: float = 0.0     # Nm
    my: float = 0.0     # Nm


@dataclass
class ComboResult:
    combo_id: str
    nodes: dict[int, NodeResult] = field(default_factory=dict)
    members: dict[int, MemberResult] = field(default_factory=dict)
    reactions: dict[int, Reaction] = field(default_factory=dict)
    second_order: bool = False
    converged: bool = True
    iterations: int = 1


@dataclass
class AnalysisResults:
    engine: str
    combos: dict[str, ComboResult] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
