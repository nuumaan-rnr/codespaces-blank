"""Engine-neutral result containers."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class NodeResult:
    ux: float = 0.0     # m
    uz: float = 0.0     # m
    ry: float = 0.0     # rad


@dataclass
class MemberResult:
    """End forces in local member axes (forces acting on the member).

    N: axial (tension positive), V: shear, M: bending about the in-plane axis.
    M_span_max: max absolute bending moment along the member.
    defl_rel_max: max transverse deflection relative to the chord between
    the member ends (the quantity checked against L/200).
    """
    N1: float = 0.0
    V1: float = 0.0
    M1: float = 0.0
    N2: float = 0.0
    V2: float = 0.0
    M2: float = 0.0
    M_span_max: float = 0.0
    defl_rel_max: float = 0.0

    @property
    def N_max_compression(self) -> float:
        """Largest compressive axial force as a positive number."""
        return max(0.0, -min(self.N1, self.N2))

    @property
    def M_abs_max(self) -> float:
        return max(abs(self.M1), abs(self.M2), abs(self.M_span_max))


@dataclass
class Reaction:
    fx: float = 0.0     # N
    fz: float = 0.0     # N
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
