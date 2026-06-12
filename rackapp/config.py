"""Input configuration for a storage rack model.

User-facing units (in YAML):
    geometry            m
    section properties  m2 / m4 / m3   (effective values per EN 15512 tests)
    E                   GPa
    fy                  MPa
    loads               kN, kN/m
    stiffness           kNm/rad
    moments             kNm

Internally everything is converted to SI base units: N, m, Pa, rad.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import yaml

KN = 1e3          # kN  -> N
KNM = 1e3         # kNm -> Nm
MPA = 1e6         # MPa -> Pa
GPA = 1e9         # GPa -> Pa


@dataclass
class GeometryConfig:
    n_bays: int = 3
    bay_width: float = 2.7              # m, system width of one bay
    level_heights: list[float] = field(default_factory=lambda: [1.5, 1.5, 1.5, 1.5])
    # level_heights[j] = vertical distance from previous level (floor for j=0)

    @property
    def level_elevations(self) -> list[float]:
        z, out = 0.0, []
        for h in self.level_heights:
            z += h
            out.append(z)
        return out

    @property
    def total_height(self) -> float:
        return sum(self.level_heights)

    @property
    def n_levels(self) -> int:
        return len(self.level_heights)

    @property
    def n_uprights(self) -> int:
        return self.n_bays + 1


@dataclass
class SectionConfig:
    """Cross-section. For perforated cold-formed rack sections use the
    *effective* properties derived from EN 15512 stub-column / bending tests."""
    name: str = "section"
    A: float = 1.0e-4                   # m2, effective area
    Iy: float = 1.0e-6                  # m4, second moment (in-plane bending)
    Wy: float = 1.0e-5                  # m3, effective section modulus
    self_weight: float = 0.0            # kg/m
    rfem_section: Optional[str] = None  # RFEM library name (analysis proxy)

    @classmethod
    def from_dict(cls, d: dict, name: str) -> "SectionConfig":
        return cls(
            name=d.get("name", name),
            A=float(d["A"]),
            Iy=float(d["Iy"]),
            Wy=float(d["Wy"]),
            self_weight=float(d.get("self_weight", 0.0)),
            rfem_section=d.get("rfem_section"),
        )


@dataclass
class MaterialConfig:
    name: str = "S355"
    E: float = 210e9                    # Pa
    fy: float = 355e6                   # Pa
    gamma_M0: float = 1.0               # cross-section resistance (EN 15512 7.5)
    gamma_M1: float = 1.0               # member buckling resistance
    density: float = 7850.0             # kg/m3 (only used if A-based self weight)

    @classmethod
    def from_dict(cls, d: dict) -> "MaterialConfig":
        return cls(
            name=d.get("name", "S355"),
            E=float(d.get("E", 210.0)) * GPA,
            fy=float(d.get("fy", 355.0)) * MPA,
            gamma_M0=float(d.get("gamma_M0", 1.0)),
            gamma_M1=float(d.get("gamma_M1", 1.0)),
            density=float(d.get("density", 7850.0)),
        )


@dataclass
class ConnectionConfig:
    """Semi-rigid connections, stiffness values from EN 15512 component tests."""
    beam_end_stiffness: float = 100e3       # Nm/rad, beam-end connector (My)
    beam_end_looseness: float = 0.005       # rad, connector looseness phi_l
    beam_end_moment_resistance: Optional[float] = None  # Nm, connector M_Rd
    base_stiffness: float = 150e3           # Nm/rad, floor/base-plate spring (My)

    @classmethod
    def from_dict(cls, d: dict) -> "ConnectionConfig":
        m_rd = d.get("beam_end_moment_resistance")
        return cls(
            beam_end_stiffness=float(d.get("beam_end_stiffness", 100.0)) * KNM,
            beam_end_looseness=float(d.get("beam_end_looseness", 0.005)),
            beam_end_moment_resistance=float(m_rd) * KNM if m_rd is not None else None,
            base_stiffness=float(d.get("base_stiffness", 150.0)) * KNM,
        )


@dataclass
class LoadConfig:
    unit_load_per_beam: float = 10e3    # N, total pallet/unit load on one beam
    beam_dead_load: float = 0.0         # N/m, additional permanent line load
    placement_load: float = 0.5e3       # N, horizontal placement load Q_ph
    placement_level: int = -1           # level index it acts at (-1 = top)

    @classmethod
    def from_dict(cls, d: dict) -> "LoadConfig":
        return cls(
            unit_load_per_beam=float(d.get("unit_load_per_beam", 10.0)) * KN,
            beam_dead_load=float(d.get("beam_dead_load", 0.0)) * KN,
            placement_load=float(d.get("placement_load", 0.5)) * KN,
            placement_level=int(d.get("placement_level", -1)),
        )


@dataclass
class ImperfectionConfig:
    """Global sway imperfection, EN 15512 (5.5.1.3 in :2009 / 8.2 in :2020).

    phi = reduction * out_of_plumb + (looseness if included)
    reduction = sqrt(0.5 * (1 + 1/n_uprights))   [multi-column reduction]

    Imperfections are applied as equivalent horizontal forces H_j = phi * V_j
    at every beam level, as permitted by the standard. All terms are
    configurable -- verify the values against the clause applicable to your
    project (the standard's editions differ in detail).
    """
    out_of_plumb: float = 1.0 / 350.0   # phi_s, erection tolerance
    include_looseness: bool = True      # add connector looseness phi_l
    min_phi: float = 1.0 / 500.0        # lower bound on total phi

    @classmethod
    def from_dict(cls, d: dict) -> "ImperfectionConfig":
        return cls(
            out_of_plumb=float(d.get("out_of_plumb", 1.0 / 350.0)),
            include_looseness=bool(d.get("include_looseness", True)),
            min_phi=float(d.get("min_phi", 1.0 / 500.0)),
        )


@dataclass
class CombinationFactors:
    """Partial factors, defaults per EN 15512:2009 Table 2."""
    gamma_G: float = 1.3                # dead loads (unfavourable)
    gamma_Q_unit: float = 1.4           # unit (pallet) loads
    gamma_Q_placement: float = 1.4      # placement loads

    @classmethod
    def from_dict(cls, d: dict) -> "CombinationFactors":
        return cls(
            gamma_G=float(d.get("gamma_G", 1.3)),
            gamma_Q_unit=float(d.get("gamma_Q_unit", 1.4)),
            gamma_Q_placement=float(d.get("gamma_Q_placement", 1.4)),
        )


@dataclass
class AnalysisConfig:
    engine: str = "internal"            # "internal" | "rfem"
    second_order: bool = True           # 2nd order (P-Delta) for ULS combos
    max_iterations: int = 15
    tolerance: float = 1e-8
    rfem_url: str = "http://localhost:8081"

    @classmethod
    def from_dict(cls, d: dict) -> "AnalysisConfig":
        return cls(
            engine=d.get("engine", "internal"),
            second_order=bool(d.get("second_order", True)),
            max_iterations=int(d.get("max_iterations", 15)),
            tolerance=float(d.get("tolerance", 1e-8)),
            rfem_url=d.get("rfem_url", "http://localhost:8081"),
        )


@dataclass
class CheckConfig:
    beam_deflection_limit: float = 200.0    # span / limit  (EN 15512: L/200)
    sway_limit: float = 200.0               # height / limit at SLS
    buckling_alpha: float = 0.34            # imperfection factor (curve b)
    K_upright: float = 1.0                  # eff. length factor; 1.0 is the
    # usual choice when the global analysis is 2nd order with imperfections

    @classmethod
    def from_dict(cls, d: dict) -> "CheckConfig":
        return cls(
            beam_deflection_limit=float(d.get("beam_deflection_limit", 200.0)),
            sway_limit=float(d.get("sway_limit", 200.0)),
            buckling_alpha=float(d.get("buckling_alpha", 0.34)),
            K_upright=float(d.get("K_upright", 1.0)),
        )


@dataclass
class RackConfig:
    name: str = "Storage rack"
    geometry: GeometryConfig = field(default_factory=GeometryConfig)
    upright_section: SectionConfig = field(default_factory=SectionConfig)
    beam_section: SectionConfig = field(default_factory=SectionConfig)
    material: MaterialConfig = field(default_factory=MaterialConfig)
    connections: ConnectionConfig = field(default_factory=ConnectionConfig)
    loads: LoadConfig = field(default_factory=LoadConfig)
    imperfections: ImperfectionConfig = field(default_factory=ImperfectionConfig)
    factors: CombinationFactors = field(default_factory=CombinationFactors)
    analysis: AnalysisConfig = field(default_factory=AnalysisConfig)
    checks: CheckConfig = field(default_factory=CheckConfig)

    @classmethod
    def from_dict(cls, d: dict) -> "RackConfig":
        geo = d.get("geometry", {})
        if "level_heights" in geo:
            heights = [float(h) for h in geo["level_heights"]]
        else:
            n = int(geo.get("n_levels", 4))
            first = float(geo.get("first_level_height", geo.get("level_spacing", 1.5)))
            spacing = float(geo.get("level_spacing", 1.5))
            heights = [first] + [spacing] * (n - 1)
        geometry = GeometryConfig(
            n_bays=int(geo.get("n_bays", 3)),
            bay_width=float(geo.get("bay_width", 2.7)),
            level_heights=heights,
        )
        sections = d.get("sections", {})
        return cls(
            name=d.get("name", "Storage rack"),
            geometry=geometry,
            upright_section=SectionConfig.from_dict(sections.get("upright", {"A": 1e-4, "Iy": 1e-6, "Wy": 1e-5}), "upright"),
            beam_section=SectionConfig.from_dict(sections.get("beam", {"A": 1e-4, "Iy": 1e-6, "Wy": 1e-5}), "beam"),
            material=MaterialConfig.from_dict(d.get("material", {})),
            connections=ConnectionConfig.from_dict(d.get("connections", {})),
            loads=LoadConfig.from_dict(d.get("loads", {})),
            imperfections=ImperfectionConfig.from_dict(d.get("imperfections", {})),
            factors=CombinationFactors.from_dict(d.get("factors", {})),
            analysis=AnalysisConfig.from_dict(d.get("analysis", {})),
            checks=CheckConfig.from_dict(d.get("checks", {})),
        )

    @classmethod
    def from_yaml(cls, path: str) -> "RackConfig":
        with open(path, "r", encoding="utf-8") as f:
            return cls.from_dict(yaml.safe_load(f) or {})

    def sway_imperfection(self) -> float:
        """Total initial sway imperfection phi (rad)."""
        import math
        n_c = self.geometry.n_uprights
        red = math.sqrt(0.5 * (1.0 + 1.0 / n_c))
        phi = red * self.imperfections.out_of_plumb
        if self.imperfections.include_looseness:
            phi += self.connections.beam_end_looseness
        return max(phi, self.imperfections.min_phi)
