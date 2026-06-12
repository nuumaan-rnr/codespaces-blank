"""Parametric generator for a complete 3D pallet-rack block:

  * upright frames (front + rear upright per frame line, braced in the
    cross-aisle plane with truss diagonals and horizontal struts),
  * pallet-beam pairs in the down-aisle direction with semi-rigid
    beam-to-upright connectors at every level,
  * semi-rigid floor connections,
  * pallet loads as UDL on the beam pairs, placement load, EN 15512
    combinations and sway imperfections.

Sections are selected by NAME from the section master library
(`SectionLibrary`), which supplies the full solver-ready property set.

Axes: X = down-aisle, Y = cross-aisle (depth), Z = up.
Node ids: frame line i (0..n_bays), side s (0 = front y=0, 1 = rear y=depth),
level j (0 = floor): id = i*1000 + s*100 + j.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from .library import SectionLibrary
from .model import (Combination, Hinge, Imperfection, LoadCase, MemberLoad,
                    NodalLoad, RackModel, Steel, Support)


@dataclass
class RackConfig:
    name: str = "pallet rack"
    # geometry
    n_bays: int = 3
    bay_width: float = 2700.0          # mm (upright centrelines, X)
    depth: float = 1100.0              # mm (front/rear upright lines, Y)
    level_heights: List[float] = field(
        default_factory=lambda: [2000.0, 2000.0, 2000.0])
    # sections: names from the master library
    library: Optional[SectionLibrary] = None     # default: bundled master
    upright_section: str = "UP-100x100x2.0"
    beam_section: str = "BM-110x50x1.5"
    brace_section: str = "BR-C40x40x2.0"
    steel_fy: float = 355.0            # MPa
    # connections (from EN 15512 Annex A tests)
    connector_stiffness: float = 1.0e8       # N*mm/rad, about local z
    connector_m_rd: Optional[float] = 2.5e6  # N*mm
    connector_looseness: float = 0.0         # rad (phi_l)
    base_stiffness: float = 5.0e8      # N*mm/rad floor connection; 0 = pinned
    # loads
    pallet_load_per_level: float = 20000.0  # N per bay per level (total)
    dead_load_beam: float = 0.05            # N/mm per beam
    placement_load: float = 500.0           # N horizontal at top (EN 15512)
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance
    mesh_beam: int = 4
    mesh_upright: int = 2


def build_rack(cfg: RackConfig) -> RackModel:
    lib = cfg.library or SectionLibrary.bundled()
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)
    up = lib.get(cfg.upright_section)
    bm = lib.get(cfg.beam_section)
    br = lib.get(cfg.brace_section)
    for sec in (up, bm, br):
        sec.material = "steel"
        m.sections[sec.name] = sec

    n_lines = cfg.n_bays + 1
    zs = [0.0]
    for h in cfg.level_heights:
        zs.append(zs[-1] + h)
    n_levels = len(zs) - 1

    def nid(i: int, s: int, j: int) -> int:
        return i * 1000 + s * 100 + j

    for i in range(n_lines):
        for s, y in ((0, 0.0), (1, cfg.depth)):
            for j, z in enumerate(zs):
                m.add_node(nid(i, s, j), i * cfg.bay_width, y, z)

    # uprights (continuous columns, one member per storey)
    mid = 1
    for i in range(n_lines):
        for s in (0, 1):
            for j in range(n_levels):
                m.add_member(mid, nid(i, s, j), nid(i, s, j + 1), up.name,
                             member_set="uprights", mesh=cfg.mesh_upright)
                mid += 1

    # pallet beams (front + rear line) with semi-rigid connectors
    beam_pairs: Dict[int, List[int]] = {}    # level -> member ids
    for j in range(1, n_levels + 1):
        beam_pairs[j] = []
        for i in range(cfg.n_bays):
            for s in (0, 1):
                m.add_member(
                    mid, nid(i, s, j), nid(i + 1, s, j), bm.name,
                    member_set="pallet beams", mesh=cfg.mesh_beam,
                    hinge_i=Hinge(rz=cfg.connector_stiffness,
                                  m_rd_z=cfg.connector_m_rd,
                                  looseness=cfg.connector_looseness),
                    hinge_j=Hinge(rz=cfg.connector_stiffness,
                                  m_rd_z=cfg.connector_m_rd,
                                  looseness=cfg.connector_looseness))
                beam_pairs[j].append(mid)
                mid += 1

    # cross-aisle frame bracing (per frame line): horizontal struts at every
    # level + alternating diagonals between front and rear uprights
    for i in range(n_lines):
        for j in range(1, n_levels + 1):
            m.add_member(mid, nid(i, 0, j), nid(i, 1, j), br.name,
                         mtype="truss", member_set="bracing")
            mid += 1
        for j in range(n_levels):
            lo, hi = (0, 1) if j % 2 == 0 else (1, 0)
            m.add_member(mid, nid(i, lo, j), nid(i, hi, j + 1), br.name,
                         mtype="truss", member_set="bracing")
            mid += 1

    # semi-rigid floor connections (rocking about both horizontal axes)
    for i in range(n_lines):
        for s in (0, 1):
            k = cfg.base_stiffness if cfg.base_stiffness > 0 else False
            m.supports.append(Support(nid(i, s, 0), ux=True, uy=True, uz=True,
                                      rx=k, ry=k, rz=False))

    # ---- load cases -------------------------------------------------------
    dead = LoadCase("dead", "permanent")
    for ids in beam_pairs.values():
        for b in ids:
            dead.member_loads.append(MemberLoad(b, qz=-cfg.dead_load_beam))
    m.load_cases["dead"] = dead

    pallets = LoadCase("pallets", "variable")
    w_line = (cfg.pallet_load_per_level / 2.0) / cfg.bay_width  # per beam line
    for ids in beam_pairs.values():
        for b in ids:
            pallets.member_loads.append(MemberLoad(b, qz=-w_line))
    m.load_cases["pallets"] = pallets

    place = LoadCase("placement", "variable")
    top = n_levels
    place.nodal_loads.append(NodalLoad(nid(0, 0, top), fx=cfg.placement_load))
    m.load_cases["placement"] = place

    place_y = LoadCase("placement_y", "variable")
    place_y.nodal_loads.append(NodalLoad(nid(0, 0, top), fy=cfg.placement_load))
    m.load_cases["placement_y"] = place_y

    # ---- combinations (EN 15512 defaults - verify for your edition) -------
    m.combinations = [
        Combination("ULS1", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q}),
        Combination("ULS2", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                     "placement": cfg.gamma_Q}),
        Combination("ULS3", "ULS",
                    {"dead": cfg.gamma_G, "pallets": cfg.gamma_Q,
                     "placement_y": cfg.gamma_Q}),
        Combination("SLS1", "SLS",
                    {"dead": 1.0, "pallets": 1.0}, imperfection=False),
        Combination("SLS2", "SLS",
                    {"dead": 1.0, "pallets": 1.0, "placement": 1.0},
                    imperfection=False),
    ]

    # ---- imperfection ------------------------------------------------------
    # phi_l: per EN 15512 the connector looseness may be omitted from phi
    # when modelled in the hinges; the builder's hinges are linear springs
    # without looseness, so it is included here.
    m.imperfection = Imperfection(
        n_cols=n_lines, phi_s=cfg.phi_s, phi_l=cfg.connector_looseness,
        method="EHF", directions=["+x", "-x", "+y", "-y"])

    return m
