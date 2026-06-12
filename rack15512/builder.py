"""Parametric generator for a complete 3D pallet-rack block:

  * upright frames (front + rear upright per frame line) braced in the
    cross-aisle plane with a D- or X-pattern:
      - horizontal strut at `bracing_start` (default 150 mm) above floor,
      - truss diagonals at `bracing_pitch` (default 600 mm) panels above it
        (zigzag for 'D', crossed pairs for 'X'),
      - no intermediate horizontals; one closing horizontal at the last
        diagonal position that fits below the frame top,
  * pallet-beam pairs in the down-aisle direction with semi-rigid
    beam-to-upright connectors, at individually specified beam levels,
  * semi-rigid floor connections - fixed stiffness, or interpolated from
    the master workbook's BASE_STIFFNESS table at the estimated upright
    axial load,
  * pallet loads as UDL on the beam pairs, placement load, EN 15512
    combinations and sway imperfections.

Sections are selected by NAME from the section master (CSV/JSON
`SectionLibrary` or .xlsx `MasterWorkbook`), which supplies the full
solver-ready property set; per-section fy values from an .xlsx master are
honoured via dedicated material entries.

Axes: X = down-aisle, Y = cross-aisle (depth), Z = up.
Node ids: frame line i (0..n_bays), side s (0 = front y=0, 1 = rear
y=depth), elevation index j (0 = floor): id = i*1000 + s*100 + j.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Union

from .library import SectionLibrary
from .master_xlsx import MasterWorkbook
from .model import (Combination, Hinge, Imperfection, LoadCase, MemberLoad,
                    NodalLoad, RackModel, Steel, Support)

_TOL = 1.0     # mm: merge coincident elevations


@dataclass
class RackConfig:
    name: str = "pallet rack"
    # geometry
    n_bays: int = 3
    bay_width: float = 2700.0          # mm (upright centrelines, X)
    depth: float = 1100.0              # mm (front/rear upright lines, Y)
    beam_levels: List[float] = field(
        default_factory=lambda: [2000.0, 4000.0, 6000.0])   # elevations [mm]
    frame_height: Optional[float] = None     # default: top beam level
    # cross-aisle frame bracing (see module docstring / drawing)
    bracing_type: str = "D"            # 'D' zigzag | 'X' crossed
    bracing_start: float = 150.0       # first horizontal above floor [mm]
    bracing_pitch: float = 600.0       # diagonal panel height [mm]
    # sections: names from the master
    library: Optional[SectionLibrary] = None     # default: bundled master
    master: Optional[MasterWorkbook] = None      # .xlsx master (overrides
    #                                              library; provides fy and
    #                                              BASE_STIFFNESS tables)
    upright_section: str = "UP-100x100x2.0"
    beam_section: str = "BM-110x50x1.5"
    brace_section: str = "BR-C40x40x2.0"
    steel_fy: float = 355.0            # MPa (sections without their own fy)
    # connections (from EN 15512 Annex A tests)
    connector_stiffness: float = 1.0e8       # N*mm/rad, about local z
    connector_m_rd: Optional[float] = 2.5e6  # N*mm
    connector_looseness: float = 0.0         # rad (phi_l)
    # floor connection: stiffness [N*mm/rad], 0 = pinned, or 'auto' =
    # interpolate the master's BASE_STIFFNESS table at the estimated
    # upright axial load (requires `master`)
    base_stiffness: Union[float, str] = 5.0e8
    # loads
    pallet_load_per_level: float = 20000.0  # N per bay per level (total)
    dead_load_beam: float = 0.05            # N/mm per beam
    placement_load: float = 500.0           # N horizontal at top (EN 15512)
    # design
    gamma_G: float = 1.3
    gamma_Q: float = 1.4
    phi_s: float = 1.0 / 350.0              # out-of-plumb tolerance
    mesh_beam: int = 4
    mesh_upright: int = 1                   # per segment between elevations


def bracing_elevations(cfg: RackConfig, frame_height: float) -> List[float]:
    """Elevations of the bracing points: start, start+pitch, ... up to the
    last position that fits at the pitch below the frame top."""
    if cfg.bracing_start > frame_height:
        return []
    zs = [cfg.bracing_start]
    while zs[-1] + cfg.bracing_pitch <= frame_height + _TOL:
        zs.append(zs[-1] + cfg.bracing_pitch)
    return zs


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
    lib = cfg.master.library if cfg.master else (cfg.library
                                                 or SectionLibrary.bundled())
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)

    up = lib.get(_pick(lib, cfg.upright_section, "upright"))
    bm = lib.get(_pick(lib, cfg.beam_section, "beam"))
    br = lib.get(_pick(lib, cfg.brace_section, "bracing"))
    for sec in (up, bm, br):
        fy = cfg.master.fy.get(sec.name) if cfg.master else None
        if fy:
            mat_name = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat_name, Steel(mat_name, fy=fy))
            sec.material = mat_name
        else:
            sec.material = "steel"
        m.sections[sec.name] = sec

    # ---- elevations --------------------------------------------------------
    beam_levels = sorted(cfg.beam_levels)
    if not beam_levels:
        raise ValueError("RackConfig.beam_levels must contain at least one level")
    H = cfg.frame_height if cfg.frame_height else beam_levels[-1]
    if H + _TOL < beam_levels[-1]:
        raise ValueError("frame_height is below the top beam level")
    brace_zs = bracing_elevations(cfg, H)

    zs: List[float] = [0.0]
    for z in sorted(set(beam_levels) | set(brace_zs) | {H}):
        if z - zs[-1] > _TOL:
            zs.append(z)

    def j_of(z: float) -> int:
        for j, zz in enumerate(zs):
            if abs(zz - z) <= _TOL:
                return j
        raise ValueError(f"elevation {z} not found")

    n_lines = cfg.n_bays + 1
    if len(zs) > 99:
        raise ValueError("too many distinct elevations for the node id scheme")

    def nid(i: int, s: int, j: int) -> int:
        return i * 1000 + s * 100 + j

    for i in range(n_lines):
        for s, y in ((0, 0.0), (1, cfg.depth)):
            for j, z in enumerate(zs):
                m.add_node(nid(i, s, j), i * cfg.bay_width, y, z)

    # ---- uprights (continuous columns, one member per elevation segment) ---
    mid = 1
    for i in range(n_lines):
        for s in (0, 1):
            for j in range(len(zs) - 1):
                m.add_member(mid, nid(i, s, j), nid(i, s, j + 1), up.name,
                             member_set="uprights", mesh=cfg.mesh_upright)
                mid += 1

    # ---- pallet beams (front + rear line) with semi-rigid connectors -------
    beam_pairs: Dict[float, List[int]] = {}
    for z in beam_levels:
        j = j_of(z)
        beam_pairs[z] = []
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
                beam_pairs[z].append(mid)
                mid += 1

    # ---- cross-aisle frame bracing per the drawing --------------------------
    # horizontal at the first bracing point, diagonals at the pitch
    # (D: zigzag, X: crossed pairs), one horizontal at the last point
    if brace_zs:
        for i in range(n_lines):
            j0, j1 = j_of(brace_zs[0]), j_of(brace_zs[-1])
            m.add_member(mid, nid(i, 0, j0), nid(i, 1, j0), br.name,
                         mtype="truss", member_set="bracing")
            mid += 1
            if len(brace_zs) > 1:
                m.add_member(mid, nid(i, 0, j1), nid(i, 1, j1), br.name,
                             mtype="truss", member_set="bracing")
                mid += 1
            for k in range(len(brace_zs) - 1):
                ja, jb = j_of(brace_zs[k]), j_of(brace_zs[k + 1])
                if cfg.bracing_type.upper() == "X":
                    m.add_member(mid, nid(i, 0, ja), nid(i, 1, jb), br.name,
                                 mtype="truss", member_set="bracing")
                    mid += 1
                    m.add_member(mid, nid(i, 1, ja), nid(i, 0, jb), br.name,
                                 mtype="truss", member_set="bracing")
                    mid += 1
                else:                                  # 'D' zigzag
                    lo, hi = (0, 1) if k % 2 == 0 else (1, 0)
                    m.add_member(mid, nid(i, lo, ja), nid(i, hi, jb), br.name,
                                 mtype="truss", member_set="bracing")
                    mid += 1

    # ---- semi-rigid floor connections ---------------------------------------
    n_uprights = 2 * n_lines
    if cfg.base_stiffness == "auto":
        if not cfg.master:
            raise ValueError("base_stiffness='auto' needs an .xlsx master "
                             "with a BASE_STIFFNESS sheet")
        # estimated ULS axial load per upright from the pallet loads
        N_est = (cfg.gamma_Q * cfg.pallet_load_per_level * cfg.n_bays
                 * len(beam_levels)) / n_uprights
        k_base, _ = cfg.master.base_stiffness(up.name, N_est)
    else:
        k_base = float(cfg.base_stiffness)
    for i in range(n_lines):
        for s in (0, 1):
            k = k_base if k_base > 0 else False
            m.supports.append(Support(nid(i, s, 0), ux=True, uy=True, uz=True,
                                      rx=k, ry=k, rz=False))

    # ---- load cases ---------------------------------------------------------
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

    top_j = j_of(beam_levels[-1])
    place = LoadCase("placement", "variable")
    place.nodal_loads.append(NodalLoad(nid(0, 0, top_j), fx=cfg.placement_load))
    m.load_cases["placement"] = place

    place_y = LoadCase("placement_y", "variable")
    place_y.nodal_loads.append(NodalLoad(nid(0, 0, top_j), fy=cfg.placement_load))
    m.load_cases["placement_y"] = place_y

    # ---- combinations (EN 15512 defaults - verify for your edition) --------
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

    # ---- imperfection --------------------------------------------------------
    # phi_l: per EN 15512 the connector looseness may be omitted from phi
    # when modelled in the hinges; the builder's hinges are linear springs
    # without looseness, so it is included here.
    m.imperfection = Imperfection(
        n_cols=n_lines, phi_s=cfg.phi_s, phi_l=cfg.connector_looseness,
        method="EHF", directions=["+x", "-x", "+y", "-y"])

    return m
