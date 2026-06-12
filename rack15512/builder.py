"""Parametric generator for a typical down-aisle pallet-rack frame:
n_bays x n_levels, uprights continuous, pallet beams with semi-rigid
beam-to-upright connectors, semi-rigid floor connections, pallet loads as
UDL on the beams.  Produces a complete RackModel ready to run."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .model import (Combination, CrossSection, Hinge, Imperfection, LoadCase,
                    MemberLoad, NodalLoad, RackModel, Steel, Support)


@dataclass
class RackConfig:
    name: str = "pallet rack"
    n_bays: int = 3
    bay_width: float = 2700.0          # mm, clear between upright centrelines
    level_heights: List[float] = field(default_factory=lambda: [2000.0, 2000.0, 2000.0])
    # sections / material
    steel_fy: float = 355.0            # MPa
    upright: Optional[CrossSection] = None
    beam: Optional[CrossSection] = None
    # connections (from EN 15512 Annex A tests)
    connector_stiffness: float = 1.0e8     # N*mm/rad
    connector_m_rd: Optional[float] = 2.5e6  # N*mm
    connector_looseness: float = 0.0       # rad (phi_l)
    base_stiffness: float = 5.0e8          # N*mm/rad floor connection; 0 = pinned
    # loads
    pallet_load_per_level: float = 20000.0  # N per bay per level (2 pallets ~ 1t each)
    dead_load_beam: float = 0.05            # N/mm self weight of beam pair
    upright_weight: float = 0.0             # N/mm (optional)
    placement_load: float = 500.0           # N horizontal at top level (EN 15512)
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance
    mesh_beam: int = 4
    mesh_upright: int = 2


def default_upright(fy: float) -> CrossSection:
    """Generic 100x100x2.0 cold-formed perforated upright (effective
    properties ~85% of gross) - replace with tested values."""
    return CrossSection("UPRIGHT-100", "steel", A=780.0, I=1.20e6, Wel=2.40e4,
                        A_eff=660.0, W_eff=2.05e4, buckling_curve="b")


def default_beam(fy: float) -> CrossSection:
    """Generic 110x50 boxed pallet beam (pair)."""
    return CrossSection("BEAM-110", "steel", A=950.0, I=2.10e6, Wel=3.80e4,
                        buckling_curve="b")


def build_rack(cfg: RackConfig) -> RackModel:
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)
    up = cfg.upright or default_upright(cfg.steel_fy)
    bm = cfg.beam or default_beam(cfg.steel_fy)
    up.material = bm.material = "steel"
    m.sections[up.name] = up
    m.sections[bm.name] = bm

    n_up = cfg.n_bays + 1
    ys = [0.0]
    for h in cfg.level_heights:
        ys.append(ys[-1] + h)

    # nodes: id = upright_index * 100 + level_index
    for i in range(n_up):
        for j, y in enumerate(ys):
            m.add_node(i * 100 + j, i * cfg.bay_width, y)

    # uprights (continuous columns, one member per storey)
    mid = 1
    for i in range(n_up):
        for j in range(len(ys) - 1):
            m.add_member(mid, i * 100 + j, i * 100 + j + 1, up.name,
                         member_set="uprights", mesh=cfg.mesh_upright,
                         k_buckling=1.0)
            mid += 1

    # pallet beams with semi-rigid connectors at every level above floor
    beam_ids: Dict[int, List[int]] = {}
    for j in range(1, len(ys)):
        beam_ids[j] = []
        for i in range(cfg.n_bays):
            h = Hinge(cfg.connector_stiffness, cfg.connector_m_rd,
                      cfg.connector_looseness)
            m.add_member(mid, i * 100 + j, (i + 1) * 100 + j, bm.name,
                         member_set="pallet beams", mesh=cfg.mesh_beam,
                         hinge_i=Hinge(h.stiffness, h.m_rd, h.looseness),
                         hinge_j=Hinge(h.stiffness, h.m_rd, h.looseness))
            beam_ids[j].append(mid)
            mid += 1

    # semi-rigid floor connections
    for i in range(n_up):
        rz = cfg.base_stiffness if cfg.base_stiffness > 0 else False
        m.supports.append(Support(i * 100, True, True, rz))

    # ---- load cases -------------------------------------------------------
    dead = LoadCase("dead", "permanent")
    for ids in beam_ids.values():
        for b in ids:
            dead.member_loads.append(MemberLoad(b, 0.0, -cfg.dead_load_beam))
    if cfg.upright_weight > 0:
        for mm in list(m.members.values()):
            if mm.member_set == "uprights":
                dead.member_loads.append(MemberLoad(mm.id, 0.0, -cfg.upright_weight))
    m.load_cases["dead"] = dead

    pallets = LoadCase("pallets", "variable")
    for ids in beam_ids.values():
        for b in ids:
            w = cfg.pallet_load_per_level / cfg.bay_width
            pallets.member_loads.append(MemberLoad(b, 0.0, -w))
    m.load_cases["pallets"] = pallets

    place = LoadCase("placement", "variable")
    top = len(ys) - 1
    place.nodal_loads.append(NodalLoad(0 * 100 + top, cfg.placement_load, 0.0, 0.0))
    m.load_cases["placement"] = place

    # ---- combinations (EN 15512 defaults - verify for your edition) -------
    m.combinations = [
        Combination("ULS1", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q}),
        Combination("ULS2", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                     "placement": cfg.gamma_Q}),
        Combination("SLS1", "SLS",
                    {"dead": 1.0, "pallets": 1.0}, imperfection=False),
        Combination("SLS2", "SLS",
                    {"dead": 1.0, "pallets": 1.0, "placement": 1.0},
                    imperfection=False),
    ]

    # ---- imperfection ------------------------------------------------------
    m.imperfection = Imperfection(
        n_cols=n_up, phi_s=cfg.phi_s,
        phi_l=cfg.connector_looseness if cfg.connector_looseness else 0.0,
        method="EHF")
    # per EN 15512, looseness already modelled in the hinges may be omitted
    # from phi; the builder includes it only if it is NOT modelled (here the
    # hinges are linear springs without looseness, so it is included).

    return m
