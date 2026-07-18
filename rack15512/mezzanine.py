"""Structural-mezzanine builder (system_type "mezzanine").

A column grid of ``mz_bays_x x mz_bays_y`` bays carries one or more floors.
Each floor is framed in up to three layers:

  columns          continuous verticals at every grid intersection, checked
                   for buckling per storey (checks.buckling_sets=["columns"])
  primary beams    column-to-column along ``mz_primary_dir`` on every grid
                   line; connection to the column is moment / pinned /
                   semi-rigid (mz_primary_conn / mz_conn_k)
  secondary beams  pin-ended, spanning perpendicular between the primary
                   lines at <= mz_secondary_spacing centres (a secondary line
                   also runs on each column line as a tie)
  joist beams      optional third pin-ended layer parallel to the primaries,
                   spanning between the secondary lines at <= mz_joist_spacing
                   centres (mz_joist_section None = no joists)

The flooring (mz_floor_type + mz_floor_dead_extra, kN/m2) and the floor live
load (mz_live_load, kN/m2) are applied as tributary-width UDLs on the topmost
modelled layer (joists when present, else the secondaries); member self-weight
is generated from each section (A * steel unit weight).  Stability comes from
vertical X-brace pairs in the outer bays of the perimeter lines
(mz_bracing / mz_braced_bays) or, with bracing off, from moment frames (the
primary connection is then forced continuous).  Sway imperfections use the
app-wide EHF method with phi_s / phi_s_cross.

Modelling note: a primary beam is split into segments at every secondary
landing (they share nodes), so member DEFLECTION reports for "primary beams"
are per segment between landings - judge the primary-span serviceability from
the floor-node displacements (SLS) as well.  Beams are assumed laterally
restrained by the decking (no LTB check).
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from .library import SectionLibrary
from .model import (Combination, Hinge, Imperfection, LoadCase, MemberLoad,
                    RackModel, Steel, Support)

# flooring dead weight [kN/m2] by type (deck + fixings, typical catalogue
# values; add services / screed etc. via mz_floor_dead_extra)
FLOOR_TYPES: Dict[str, float] = {
    "Chequered plate 3 mm": 0.28,
    "Chequered plate 4 mm": 0.36,
    "Chipboard P6 38 mm": 0.30,
    "Plywood 18 mm": 0.15,
    "Open steel grating": 0.45,
    "Composite deck + 100 mm concrete": 2.60,
    "None / custom (use extra)": 0.0,
}

_GAMMA_STEEL = 7.698e-5          # N/mm^3
_KNM2 = 1.0e-3                   # kN/m^2 -> N/mm^2


def _spaced(length: float, spacing: float) -> List[float]:
    """Uniform positions 0..length at centres <= spacing (ends included)."""
    n = max(1, int(math.ceil(length / max(spacing, 1.0))))
    return [length * i / n for i in range(n + 1)]


def build_mezzanine(cfg) -> RackModel:
    lib = cfg.master.library if cfg.master else (cfg.library
                                                 or SectionLibrary.bundled())
    m = RackModel(name=cfg.name)
    m.materials["steel"] = Steel("steel", fy=cfg.steel_fy)

    def pick(name: Optional[str], *roles: str):
        if name and name in lib.sections:
            return lib.get(name)
        for role in roles:
            cands = lib.names(role)
            if cands:
                return lib.get(cands[0])
        return lib.get(lib.names()[0])

    col = pick(cfg.mz_column_section, "column", "upright")
    prim = pick(cfg.mz_primary_section, "beam")
    sec = pick(cfg.mz_secondary_section, "beam")
    joist = pick(cfg.mz_joist_section, "beam") if cfg.mz_joist_section else None
    brace = pick(cfg.mz_brace_section or cfg.brace_section, "bracing")
    for s in {x.name: x for x in
              ([col, prim, sec, brace] + ([joist] if joist else []))}.values():
        fy = (cfg.master.fy.get(s.name)
              if (cfg.master and not cfg.fy_override) else None)
        if fy:
            mat = f"steel_fy{fy:.0f}"
            m.materials.setdefault(mat, Steel(mat, fy=fy))
            s.material = mat
        else:
            s.material = "steel"
        if not s.J or s.J <= 0:
            s.J = max(s.A * (s.t or 2.0) ** 2 / 3.0, 1.0)
        m.sections[s.name] = s

    # ---- grid ---------------------------------------------------------------
    nx, ny = int(cfg.mz_bays_x), int(cfg.mz_bays_y)
    bx, by = float(cfg.mz_bay_x), float(cfg.mz_bay_y)
    if nx < 1 or ny < 1:
        raise ValueError("mezzanine needs at least a 1 x 1 column grid")
    floors = [cfg.mz_floor_height * (f + 1)
              for f in range(max(1, int(cfg.mz_n_floors)))]
    H = floors[-1]
    # primary direction p; q is the perpendicular in-plan axis
    along_x = str(cfg.mz_primary_dir).upper() != "Y"
    n_p, n_q = (nx, ny) if along_x else (ny, nx)
    b_p, b_q = (bx, by) if along_x else (by, bx)
    L_p, L_q = n_p * b_p, n_q * b_q

    def xy(p: float, q: float) -> Tuple[float, float]:
        return (p, q) if along_x else (q, p)

    nid_of: Dict[Tuple[int, int, int], int] = {}
    _next = [1]

    def node_at(x: float, y: float, z: float) -> int:
        key = (round(x), round(y), round(z))
        nid = nid_of.get(key)
        if nid is None:
            nid = _next[0]
            _next[0] += 1
            nid_of[key] = nid
            m.add_node(nid, x, y, z)
        return nid

    mid = [0]

    def add(ni: int, nj: int, section, **kw):
        mid[0] += 1
        return m.add_member(mid[0], ni, nj, section.name, **kw)

    # ---- columns (continuous, one member per storey) -----------------------
    storeys = [0.0] + floors
    for ip in range(n_p + 1):
        for iq in range(n_q + 1):
            x, y = xy(ip * b_p, iq * b_q)
            lbl = f"Column {chr(65 + (ip % 26))}{iq + 1}"
            for f in range(len(floors)):
                h = storeys[f + 1] - storeys[f]
                add(node_at(x, y, storeys[f]), node_at(x, y, storeys[f + 1]),
                    col, member_set="columns", set_label=lbl,
                    L_buckling_y=h, L_buckling_z=h, L_torsion=h)
            m.supports.append(Support(node_at(x, y, 0.0), ux=True, uy=True,
                                      uz=True, rx=bool(cfg.mz_base_fixed),
                                      ry=bool(cfg.mz_base_fixed), rz=True))

    # ---- connections --------------------------------------------------------
    braced = bool(cfg.mz_bracing)
    conn = str(cfg.mz_primary_conn).lower()
    if not braced and conn != "moment":
        conn = "moment"                      # unbraced -> moment frame
    if conn == "pinned":
        end_hinge = Hinge(rz=0.0, ry=0.0)
    elif conn in ("semi", "semi-rigid") and cfg.mz_conn_k:
        end_hinge = Hinge(rz=float(cfg.mz_conn_k), ry=0.0)
    else:
        end_hinge = None                     # continuous (moment)
    pin = Hinge(rz=0.0, ry=0.0)

    def copy_h(h: Optional[Hinge]) -> Optional[Hinge]:
        return Hinge(rz=h.rz, ry=h.ry, rx=h.rx) if h else None

    # ---- floor framing ------------------------------------------------------
    sec_pos = _spaced(L_p, float(cfg.mz_secondary_spacing))
    top_layer: List[Tuple[int, float]] = []        # (member id, trib width)
    for z in floors:
        # primary beams along p on every q grid line, split at sec_pos
        for iq in range(n_q + 1):
            for ip in range(n_p):
                p0, p1 = ip * b_p, (ip + 1) * b_p
                pts = sorted({p0, p1, *[p for p in sec_pos
                                        if p0 + 1e-6 < p < p1 - 1e-6]})
                lbl = f"PB {chr(65 + (ip % 26))}{iq + 1} z{z:.0f}"
                for k in range(len(pts) - 1):
                    x0, y0 = xy(pts[k], iq * b_q)
                    x1, y1 = xy(pts[k + 1], iq * b_q)
                    add(node_at(x0, y0, z), node_at(x1, y1, z), prim,
                        member_set="primary beams", set_label=lbl, mesh=2,
                        hinge_i=copy_h(end_hinge) if k == 0 else None,
                        hinge_j=copy_h(end_hinge)
                        if k == len(pts) - 2 else None)
        # secondary beams along q between adjacent primary lines
        joist_pos = (_spaced(L_q, float(cfg.mz_joist_spacing))
                     if joist else [])
        sec_trib = {p: 0.5 * ((sec_pos[min(i + 1, len(sec_pos) - 1)]
                               - sec_pos[max(i - 1, 0)]))
                    for i, p in enumerate(sec_pos)}
        for p in sec_pos:
            for iq in range(n_q):
                q0, q1 = iq * b_q, (iq + 1) * b_q
                pts = sorted({q0, q1, *[q for q in joist_pos
                                        if q0 + 1e-6 < q < q1 - 1e-6]})
                for k in range(len(pts) - 1):
                    x0, y0 = xy(p, pts[k])
                    x1, y1 = xy(p, pts[k + 1])
                    mm = add(node_at(x0, y0, z), node_at(x1, y1, z), sec,
                             member_set="secondary beams", mesh=2,
                             hinge_i=copy_h(pin) if k == 0 else None,
                             hinge_j=copy_h(pin)
                             if k == len(pts) - 2 else None)
                    if not joist:
                        top_layer.append((mm.id, sec_trib[p]))
        # joists along p between adjacent secondary lines
        if joist:
            j_trib = {q: 0.5 * ((joist_pos[min(i + 1, len(joist_pos) - 1)]
                                 - joist_pos[max(i - 1, 0)]))
                      for i, q in enumerate(joist_pos)}
            for q in joist_pos:
                for i in range(len(sec_pos) - 1):
                    x0, y0 = xy(sec_pos[i], q)
                    x1, y1 = xy(sec_pos[i + 1], q)
                    mm = add(node_at(x0, y0, z), node_at(x1, y1, z), joist,
                             member_set="joists", mesh=2,
                             hinge_i=copy_h(pin), hinge_j=copy_h(pin))
                    top_layer.append((mm.id, j_trib[q]))

    # ---- vertical bracing (X-pairs in the outer bays of perimeter lines) ---
    if braced:
        nb = max(1, int(cfg.mz_braced_bays))

        def brace_bay(xy0: Tuple[float, float], xy1: Tuple[float, float]):
            for f in range(len(floors)):
                z0, z1 = storeys[f], storeys[f + 1]
                a0 = node_at(*xy0, z0)
                a1 = node_at(*xy0, z1)
                b0 = node_at(*xy1, z0)
                b1 = node_at(*xy1, z1)
                add(a0, b1, brace, mtype="truss", member_set="bracing")
                add(b0, a1, brace, mtype="truss", member_set="bracing")

        for iq in (0, n_q):                     # p-direction walls
            for ip in list(range(nb)) + list(range(n_p - nb, n_p)):
                brace_bay(xy(ip * b_p, iq * b_q), xy((ip + 1) * b_p,
                                                     iq * b_q))
        for ip in (0, n_p):                     # q-direction walls
            for iq in list(range(nb)) + list(range(n_q - nb, n_q)):
                brace_bay(xy(ip * b_p, iq * b_q), xy(ip * b_p,
                                                     (iq + 1) * b_q))

    # ---- loads --------------------------------------------------------------
    q_dead = (FLOOR_TYPES.get(cfg.mz_floor_type, 0.0)
              + float(cfg.mz_floor_dead_extra)) * _KNM2      # N/mm^2
    q_live = float(cfg.mz_live_load) * _KNM2
    dead = LoadCase("dead", "permanent")
    if cfg.include_self_weight:
        for mm in m.members.values():
            s = m.sections[mm.section]
            dead.member_loads.append(MemberLoad(mm.id,
                                                qz=-s.A * _GAMMA_STEEL))
    live = LoadCase("live", "variable")
    for mid_, trib in top_layer:
        if q_dead > 0:
            dead.member_loads.append(MemberLoad(mid_, qz=-q_dead * trib))
        if q_live > 0:
            live.member_loads.append(MemberLoad(mid_, qz=-q_live * trib))
    m.load_cases["dead"] = dead
    m.load_cases["live"] = live

    # ---- combinations & imperfection ---------------------------------------
    sls_order = 1 if cfg.sls_first_order else None
    m.combinations = [
        Combination("ULS1", "ULS", {"dead": cfg.gamma_G, "live": cfg.gamma_Q}),
        Combination("SLS1", "SLS", {"dead": 1.0, "live": 1.0},
                    order=sls_order),
    ]
    m.imperfection = Imperfection(
        n_cols=n_p + 1, phi_s=cfg.phi_s, phi_s_cross=cfg.phi_s_cross,
        method="EHF", standard="EN1993", height=H,
        directions=["+x", "-x", "+y", "-y"])
    m.checks.buckling_sets = ["columns"]
    m.analysis.stiffness_gamma_m = cfg.stiffness_gamma_m
    return m
