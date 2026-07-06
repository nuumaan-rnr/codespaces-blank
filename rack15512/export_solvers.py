"""Export a RackModel to solver input files so a project can be re-run in
RSTAB or STAAD.Pro instead of (or to cross-check) the OpenSeesPy engine.

ADDITIVE only - reads a RackModel, writes input decks; no engine changes.

  * to_staad(model, path)       -> COMPLETE STAAD.Pro .std input: geometry,
                                   per-member prismatic properties with the
                                   correct bending-plane mapping, materials,
                                   spring supports and beam-end connector
                                   moment springs (per-DEGREE constants, the
                                   STAAD convention), truss braces, every
                                   load case and every generated combination
                                   as a REPEAT LOAD primary case whose sway
                                   imperfection is a NOTIONAL LOAD block
                                   (gamma * phi on the gravity cases),
                                   followed by a P-Delta analysis - open
                                   and Run.
  * to_rstab8_xlsx(model, path) -> RSTAB 8 table workbook (File > Import >
                                   Microsoft Excel); sheets mirror the RSTAB
                                   data tables.  Imperfections are TWO
                                   native inclination load cases (Imp X
                                   L/300, Imp Y L/200 on the upright member
                                   sets, table 3.4) referenced by the
                                   combinations with factor +1 / -1 - the
                                   same structure as an RSTAB-authored
                                   model.
  * to_rstab_xlsx(model, path)  -> legacy loose table workbook (kept for
                                   compatibility).

Axis conventions: the app uses Z up (gravity -Z), X down-aisle, Y cross-
aisle.  STAAD SPACE uses Y up -> coordinates are mapped
(X, Y, Z)_staad = (X_app, Z_app, Y_app) and gravity acts in -Y; the app
+y sway direction is STAAD Z.  RSTAB's global Z points DOWN ->
Z_rstab = -Z_app.

Imperfections: the app engine applies the sway imperfection as an initial
out-of-plumb of the geometry.  Each solver's NATIVE equivalent is used:
RSTAB inclination load cases (1/300 down-aisle, 1/200 cross-aisle on the
continuous upright sets) and STAAD notional loads (horizontal joint loads
generated as factor x the vertical loads of the referenced gravity cases,
factor = gamma * phi per combination) - both scale exactly like the
engine's (gamma * gravity) tilt.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List

from .model import RackModel

_DEG = math.pi / 180.0        # STAAD rotational springs are per DEGREE


def _members_of(model: RackModel):
    return sorted(model.members.values(), key=lambda m: m.id)


def _node_map(model: RackModel) -> Dict[int, int]:
    """1-based node id remap (STAAD/RSTAB joints must be >= 1; app uses 0-based)."""
    return {nid: i + 1 for i, nid in enumerate(sorted(model.nodes))}


def _udl_load_case(model: RackModel):
    """Legacy helper: characteristic gravity member UDLs [N/mm] (down = -Z)
    from the 'pallets' + 'dead' load cases, keyed by member id."""
    q: Dict[int, float] = {}
    for lc in model.load_cases.values():
        if lc.name not in ("pallets", "dead"):
            continue
        for ml in getattr(lc, "member_loads", []):
            q[ml.member] = q.get(ml.member, 0.0) + getattr(ml, "qz", 0.0)
    return q


def _id_ranges(ids) -> str:
    """RSTAB member/node list syntax: '1-5,8,10-12'."""
    ids = sorted(set(int(i) for i in ids))
    if not ids:
        return ""
    out, a, b = [], ids[0], ids[0]
    for i in ids[1:]:
        if i == b + 1:
            b = i
            continue
        out.append(f"{a}-{b}" if b > a else f"{a}")
        a = b = i
    out.append(f"{a}-{b}" if b > a else f"{a}")
    return ",".join(out)


def _staad_ranges(ids) -> List[str]:
    """STAAD list syntax parts: '1 TO 5', '8', '10 TO 12'."""
    ids = sorted(set(int(i) for i in ids))
    out: List[str] = []
    a = b = None
    for i in ids:
        if a is None:
            a = b = i
            continue
        if i == b + 1:
            b = i
            continue
        out.append(f"{a} TO {b}" if b > a else f"{a}")
        a = b = i
    if a is not None:
        out.append(f"{a} TO {b}" if b > a else f"{a}")
    return out


def _chunk(parts: List[str], per_line: int = 9) -> List[str]:
    return [" ".join(parts[i:i + per_line])
            for i in range(0, len(parts), per_line)]


def _member_length(model: RackModel, m) -> float:
    ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
    return math.dist((ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z))


def _is_vertical(model: RackModel, m) -> bool:
    ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
    return abs(ni.x - nj.x) < 1e-6 and abs(ni.y - nj.y) < 1e-6


# --------------------------------------------------------- imperfections
def _imp_directions(model: RackModel) -> List[str]:
    """Sway directions actually used by the model's combinations."""
    imp = model.imperfection
    dirs: List[str] = []
    for c in model.combinations:
        if not c.imperfection:
            continue
        for d in (c.imp_directions or (imp.directions if imp else [])):
            if d not in dirs:
                dirs.append(d)
    return dirs


def _gravity_cases(model: RackModel) -> List[str]:
    """Load cases that carry vertical (gravity) loads - the sources the
    sway imperfection acts on."""
    out: List[str] = []
    for nm, lc in model.load_cases.items():
        if any(ml.qz < -1e-12 for ml in lc.member_loads) or \
           any(nl.fz < -1e-12 for nl in lc.nodal_loads):
            out.append(nm)
    return out


def _combo_rows(model: RackModel) -> List[dict]:
    """One expanded combination per (combination x imperfection direction):
    [{'name', 'kind', 'ds', 'method', 'imp': direction or None,
      'factors': [(load_case_name, factor), ...]}]."""
    imp = model.imperfection
    out: List[dict] = []
    for c in model.combinations:
        dirs = [None]
        if c.imperfection and imp:
            dirs = c.imp_directions or imp.directions
        for d in dirs:
            ds = ("ACC" if any(k.startswith("accidental") for k in c.factors)
                  else c.kind)
            out.append({
                "name": c.name + (f" (imp {d})" if d else ""),
                "kind": c.kind, "ds": ds, "imp": d,
                "method": ("Second order analysis (P-Delta)"
                           if c.kind == "ULS"
                           else "Geometrically linear analysis"),
                "factors": list(c.factors.items()),
            })
    return out


# ----------------------------------------------------------------- STAAD .std
def to_staad(model: RackModel, path: str) -> str:
    """Write a COMPLETE, runnable STAAD.Pro .std input deck (mm, N):
    geometry, prismatic properties (bending planes mapped per member
    orientation), materials, truss braces, connector moment springs and
    support springs (converted to STAAD's per-degree constants), every
    load case, and every combination as a REPEAT LOAD primary case with a
    NOTIONAL LOAD block for the sway imperfection (factor = gamma * phi
    on each gravity case), solved by a P-Delta analysis."""
    nmap = _node_map(model)
    imp = model.imperfection
    grav = set(_gravity_cases(model))
    L: List[str] = []
    L.append("STAAD SPACE " + (model.name or "RACK")[:60])
    L.append("START JOB INFORMATION")
    L.append("ENGINEER DATE " + (model.name or ""))
    L.append("END JOB INFORMATION")
    L.append("* Exported from Racks & Rollers (EN 15512 app).")
    L.append("* App axes Z-up mapped to STAAD Y-up: (x,y,z)_staad =")
    L.append("* (X, Z, Y)_app; gravity = -Y.  X = down-aisle, Z = cross-aisle.")
    L.append("* Sway imperfections: NOTIONAL LOAD blocks inside each")
    L.append("* combination (factor = gamma * phi per gravity case;")
    L.append("* phi = 1/300 down-aisle X, 1/200 cross-aisle Z by default).")
    L.append("UNIT MMS NEWTON")

    L.append("JOINT COORDINATES")
    for n in sorted(model.nodes.values(), key=lambda n: n.id):
        L.append(f"{nmap[n.id]} {n.x:.4f} {n.z:.4f} {n.y:.4f};")

    L.append("MEMBER INCIDENCES")
    for m in _members_of(model):
        L.append(f"{m.id} {nmap[m.node_i]} {nmap[m.node_j]};")

    L.append("DEFINE MATERIAL START")
    for mat in model.materials.values():
        nm = mat.name.replace(" ", "_")
        L.append(f"ISOTROPIC {nm}")
        L.append(f"E {mat.E}")
        L.append(f"POISSON {getattr(mat, 'nu', 0.3)}")
        L.append("DENSITY 7.85e-08")
        L.append(f"G {mat.G}")
    L.append("END DEFINE MATERIAL")

    # prismatic properties; bending-plane mapping:
    #   vertical member (upright): STAAD local z // global Z_staad
    #     (= cross-aisle) -> MZ/IZ = down-aisle flexure = app Iz;  IY = app Iy
    #   horizontal member: STAAD local y is up -> gravity bending is MZ/IZ
    #     -> IZ = app strong axis Iy;  IY = app Iz
    L.append("MEMBER PROPERTY AMERICAN")
    for m in _members_of(model):
        s = model.section_of(m)
        a = s.A * (m.area_factor or 1.0)
        if _is_vertical(model, m):
            iy, iz = s.Iy, s.Iz
        else:
            iy, iz = s.Iz, s.Iy
        L.append(f"{m.id} PRIS AX {a:.3f} IX {s.J:.1f} IY {iy:.1f} "
                 f"IZ {iz:.1f}")

    L.append("CONSTANTS")
    by_mat: Dict[str, List[int]] = {}
    for m in _members_of(model):
        by_mat.setdefault(model.material_of(m).name.replace(" ", "_"),
                          []).append(m.id)
    for nm, mids in by_mat.items():
        for part in _chunk(_staad_ranges(mids)):
            L.append(f"MATERIAL {nm} MEMB {part}")

    trusses = [m.id for m in _members_of(model) if m.mtype == "truss"]
    if trusses:
        L.append("MEMBER TRUSS")
        L.extend(_chunk(_staad_ranges(trusses)))

    # beam-end connector springs: STAAD member-release moment springs are
    # entered per DEGREE -> k_deg = k_rad * pi/180 (about the beam's strong
    # axis = STAAD MZ)
    rel: List[str] = []
    for m in _members_of(model):
        for end, h in (("START", m.hinge_i), ("END", m.hinge_j)):
            if h is None:
                continue
            kz = getattr(h, "rz", None)
            if isinstance(kz, (int, float)) and kz > 0:
                rel.append(f"{m.id} {end} KMZ {kz * _DEG:.1f}")
            elif kz == 0:
                rel.append(f"{m.id} {end} MZ")
    if rel:
        L.append("MEMBER RELEASE")
        L.extend(rel)

    # supports: translations fixed; app rotational DOFs map to STAAD as
    #   app rx (about X_app) -> MX;  app ry (about Y_app = Z_staad) -> MZ;
    #   app rz (about Z_app = Y_staad) -> MY.  Springs per DEGREE.
    L.append("SUPPORTS")
    sup_groups: Dict[tuple, List[int]] = {}
    for sup in model.supports:
        key = (sup.rx if not isinstance(sup.rx, float) else round(sup.rx, 3),
               sup.ry if not isinstance(sup.ry, float) else round(sup.ry, 3),
               sup.rz if not isinstance(sup.rz, float) else round(sup.rz, 3))
        sup_groups.setdefault(key, []).append(nmap[sup.node])
    for (rx, ry, rz), nodes in sup_groups.items():
        rel_dofs, springs = [], []
        for app_dof, staad_m, staad_k in ((rx, "MX", "KMX"),
                                          (ry, "MZ", "KMZ"),
                                          (rz, "MY", "KMY")):
            if isinstance(app_dof, (int, float)) and app_dof > 0:
                springs.append(f"{staad_k} {app_dof * _DEG:.1f}")
            elif app_dof is not True:
                rel_dofs.append(staad_m)
        cond = "FIXED BUT " + " ".join(rel_dofs + springs)
        for part in _chunk(_staad_ranges(nodes)):
            L.append(f"{part} {cond.strip()}")
    if getattr(model, "base_axial_table", None):
        L.append("* NOTE: the app runs the base rotational spring as an")
        L.append("* AXIAL-DEPENDENT diagram (see the report / RSTAB export")
        L.append("* sheet 1.8.7); the constant above is the linear value.")

    # ---- primary load cases ------------------------------------------------
    lc_no = {nm: i + 1 for i, nm in enumerate(model.load_cases)}
    LOADTYPE = {"dead": "Dead", "pallets": "Live", "pallets_pattern": "Live",
                "placement": "Live", "placement_lo": "Live",
                "placement_y": "Live", "accidental_x": "Accidental",
                "accidental_y": "Accidental"}
    for nm, lc in model.load_cases.items():
        L.append(f"LOAD {lc_no[nm]} LOADTYPE {LOADTYPE.get(nm, 'Live')} "
                 f"TITLE {nm.upper()}")
        byq: Dict[float, List[int]] = {}
        for ml in lc.member_loads:
            if abs(ml.qz) > 1e-12:
                byq.setdefault(round(ml.qz, 6), []).append(ml.member)
        if byq:
            L.append("MEMBER LOAD")
            for q, mids in sorted(byq.items()):
                for part in _chunk(_staad_ranges(mids)):
                    L.append(f"{part} UNI GY {q:.6f}")
        if lc.nodal_loads:
            L.append("JOINT LOAD")
            for nl in lc.nodal_loads:
                comps = []
                if abs(nl.fx) > 1e-9:
                    comps.append(f"FX {nl.fx:.3f}")
                if abs(nl.fy) > 1e-9:
                    comps.append(f"FZ {nl.fy:.3f}")     # app Y -> STAAD Z
                if abs(nl.fz) > 1e-9:
                    comps.append(f"FY {nl.fz:.3f}")     # app Z -> STAAD Y
                if comps:
                    L.append(f"{nmap[nl.node]} " + " ".join(comps))

    # ---- combinations as REPEAT LOAD primary cases + P-Delta --------------
    L.append("* Combinations: REPEAT LOAD primary cases (required for the")
    L.append("* P-Delta analysis to include the secondary effects), each")
    L.append("* with its NOTIONAL LOAD sway imperfection.  SLS cases run")
    L.append("* in the same P-Delta batch (slightly conservative vs the")
    L.append("* app's geometrically linear SLS).")
    co = 100
    for row in _combo_rows(model):
        co += 1
        L.append(f"LOAD {co} LOADTYPE None TITLE {row['ds']} {row['name']}")
        L.append("REPEAT LOAD")
        L.extend(_chunk([f"{lc_no[k]} {f:g}" for k, f in row["factors"]],
                        per_line=8))
        d = row["imp"]
        if d:
            phi = imp.value_for(d) if imp else 1.0 / 300.0
            sgn = 1.0 if d[0] == "+" else -1.0
            axis = "X" if "x" in d else "Z"             # app +y -> STAAD Z
            parts = [f"{lc_no[k]} {axis} {sgn * f * phi:.6f}"
                     for k, f in row["factors"] if k in grav]
            if parts:
                L.append("NOTIONAL LOAD")
                L.extend(_chunk(parts, per_line=6))
    L.append("PDELTA 30 ANALYSIS SMALLDELTA")
    L.append("FINISH")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


# ------------------------------------------------- legacy RSTAB loose .xlsx
def to_rstab_xlsx(model: RackModel, path: str) -> str:
    """Legacy loose RSTAB/RFEM table workbook (kept for compatibility);
    use to_rstab8_xlsx for the RSTAB 8 import layout."""
    import openpyxl
    wb = openpyxl.Workbook()

    nmap = _node_map(model)
    ws = wb.active
    ws.title = "1.1 Nodes"
    ws.append(["No.", "X [mm]", "Y [mm]", "Z [mm]"])
    for n in sorted(model.nodes.values(), key=lambda n: n.id):
        ws.append([nmap[n.id], n.x, n.y, n.z])

    ws = wb.create_sheet("1.2 Materials")
    ws.append(["No.", "Description", "E [N/mm2]", "G [N/mm2]", "nu", "fy [N/mm2]"])
    mats = {m.name: m for m in model.materials.values()}
    midx = {nm: i + 1 for i, nm in enumerate(mats)}
    for nm, m in mats.items():
        ws.append([midx[nm], nm, m.E, m.G, getattr(m, "nu", 0.3), m.fy])

    ws = wb.create_sheet("1.3 Cross-Sections")
    ws.append(["No.", "Description", "Material No.", "A [mm2]", "Iy [mm4]",
               "Iz [mm4]", "J [mm4]", "Wely [mm3]", "Welz [mm3]"])
    secs = {s.name: s for s in model.sections.values()}
    sidx = {nm: i + 1 for i, nm in enumerate(secs)}
    for nm, s in secs.items():
        ws.append([sidx[nm], nm, midx.get(s.material, 1), s.A, s.Iy, s.Iz,
                   s.J, s.Wely, s.Welz])

    ws = wb.create_sheet("1.7 Members")
    ws.append(["No.", "Start Node", "End Node", "Cross-Section No.",
               "Start Hinge", "End Hinge", "Member Set"])
    hinges: List = []

    def hinge_id(h):
        if h is None:
            return ""
        for i, hh in enumerate(hinges):
            if (hh.rx, hh.ry, hh.rz) == (h.rx, h.ry, h.rz):
                return i + 1
        hinges.append(h)
        return len(hinges)
    for m in _members_of(model):
        ws.append([m.id, nmap[m.node_i], nmap[m.node_j],
                   sidx.get(model.section_of(m).name, 1),
                   hinge_id(m.hinge_i), hinge_id(m.hinge_j), m.member_set])

    ws = wb.create_sheet("1.4 Member Hinges")
    ws.append(["No.", "phi-x [Nmm/rad]", "phi-y [Nmm/rad]", "phi-z [Nmm/rad]",
               "M_Rd,z [Nmm]", "comment"])
    for i, h in enumerate(hinges):
        ws.append([i + 1, h.rx or "free", h.ry or "free", h.rz or "free",
                   getattr(h, "m_rd_z", None), "beam-end connector"])

    ws = wb.create_sheet("1.8 Nodal Supports")
    ws.append(["On Nodes", "uX", "uY", "uZ", "phi-X [Nmm/rad]",
               "phi-Y [Nmm/rad]", "phi-Z [Nmm/rad]"])

    def cell(v):
        if v is True:
            return "fixed"
        if not v:
            return "free"
        return v
    for sup in model.supports:
        ws.append([nmap[sup.node], cell(sup.ux), cell(sup.uy), cell(sup.uz),
                   cell(sup.rx), cell(sup.ry), cell(sup.rz)])

    ws = wb.create_sheet("LC1 Member Loads")
    ws.append(["On Members", "Type", "Direction", "p [N/mm]", "comment"])
    q = _udl_load_case(model)
    for mid, qz in q.items():
        if abs(qz) > 1e-9:
            ws.append([mid, "Force", "Z (down)", qz, "pallet+dead characteristic"])

    ws = wb.create_sheet("README")
    for row in [
        ["Exported from Racks & Rollers (EN 15512 app) for RSTAB/RFEM import."],
        ["Legacy loose layout - use the RSTAB8 export for the import-ready"],
        ["RSTAB 8 data-table workbook with loads, combinations and native"],
        ["imperfection load cases."],
    ]:
        ws.append(row)

    wb.save(path)
    return path


def export_project(model_json: str, out_dir: str, name: str = "model") -> dict:
    """Load a saved project model.json and write the solver decks."""
    import os
    from . import io_json
    os.makedirs(out_dir, exist_ok=True)
    model = io_json.load(model_json)
    std = to_staad(model, os.path.join(out_dir, f"{name}.std"))
    xlsx = to_rstab_xlsx(model, os.path.join(out_dir, f"{name}_RSTAB.xlsx"))
    x8 = to_rstab8_xlsx(model, os.path.join(out_dir, f"{name}_RSTAB8.xlsx"))
    return {"staad": std, "rstab_xlsx": xlsx, "rstab8_xlsx": x8,
            "nodes": len(model.nodes), "members": len(model.members)}


# ------------------------------------------------------- RSTAB 8 table .xlsx
# Sheet names, column layouts, units and conventions mirror the RSTAB 8 data
# tables (validated against an RSTAB 8.29 model printout):
#   1.1 Nodes [mm, global Z DOWN]          1.8.7 Support stiffness diagram
#   1.2 Materials [kN/cm2]                 1.11 Sets of Members
#   1.3 Cross-Sections [cm2, cm4]          2.1 Load Cases (+ 2 imp. LCs)
#   1.3.2 Stiffness reduction (braces)     2.5 Load Combinations
#   1.4 Member Hinges [kNcm/rad]           3.1/3.2 Loads [kN, kN/m]
#   1.7 Members / 1.8 Nodal Supports       3.4 Imperfections (inclinations)
_RSTAB_SECTION_MAP = {
    # app section name -> RSTAB library / SHAPE-THIN description
    "1C36X21X1.2": "SHAPE-THIN B5H36X21T012",
}


def _rstab_section_name(name: str) -> str:
    """RSTAB description for an app section: known mappings, RRO-PAR for
    cold-formed RHS names (RHS<h>X<b>X<t>), SHAPE-THIN <name> otherwise."""
    if name in _RSTAB_SECTION_MAP:
        return _RSTAB_SECTION_MAP[name]
    m = re.match(r"RHS\s*(\d+)\s*X\s*(\d+)\s*X\s*([\d.]+)$", name.upper())
    if m:
        h, b, t = m.group(1), m.group(2), m.group(3)
        return f"RRO-PAR {h}/{b}/{t}/3.2/1.6/K"
    return f"SHAPE-THIN {name}"


def _rstab_material_name(mat) -> str:
    """Suggested RSTAB material library entry for an app Steel."""
    E, fy = mat.E, mat.fy or 0.0
    if abs(E - 200000.0) < 1.0:                       # IS 2062 basis
        if fy > 310.0:
            return "Steel IS 2062 E 350 (Fe 490) | IS 800:2007"
        return "Steel IS 2062 E 250 (Fe 410 W) A | IS 800:2007"
    if abs(E - 210000.0) < 1.0:                       # EN basis
        return ("Steel S 355 | DIN 18800-1:2008-11" if fy >= 355.0
                else "Steel S 235 | DIN 18800-1:2008-11")
    return f"User steel E={E:.0f} N/mm2, fy={fy:.0f} N/mm2"


def to_rstab8_xlsx(model: RackModel, path: str) -> str:
    """Write an RSTAB 8 table workbook of the whole model - geometry,
    materials, cross-sections (RSTAB library names), member hinges, supports
    (linear spring + the axial-dependent base stiffness diagram sheet), sets
    of members, load cases with TWO native imperfection load cases (Imp X
    L/300, Imp Y L/200 as inclinations on the upright member sets, table
    3.4), every load and the generated combinations referencing the
    imperfection cases with factor +1 / -1 - the same structure as an
    RSTAB-authored model.  Import via File > Import > Microsoft Excel.
    Returns the path."""
    import openpyxl
    wb = openpyxl.Workbook()
    nmap = _node_map(model)
    imp = model.imperfection
    dirs = _imp_directions(model)

    # ---- 1.1 Nodes (RSTAB global Z points DOWN; the app Z points UP) -----
    ws = wb.active
    ws.title = "1.1 Nodes"
    ws.append(["Node No.", "Reference Node", "Coordinate System",
               "X [mm]", "Y [mm]", "Z [mm]"])
    for n in sorted(model.nodes.values(), key=lambda n: n.id):
        ws.append([nmap[n.id], "-", "Cartesian", n.x, n.y, -n.z])

    # ---- 1.2 Materials [kN/cm2] ------------------------------------------
    ws = wb.create_sheet("1.2 Materials")
    ws.append(["Matl. No.", "Description (RSTAB library)",
               "Modulus E [kN/cm2]", "Modulus G [kN/cm2]",
               "Spec. Weight [kN/m3]", "Coeff. of Th. Exp. [1/degC]",
               "Partial Factor gamma_M [-]", "Material Model",
               "fy [N/mm2] (app)"])
    mats = {m.name: m for m in model.materials.values()}
    midx = {nm: i + 1 for i, nm in enumerate(mats)}
    for nm, m in mats.items():
        ws.append([midx[nm], _rstab_material_name(m), m.E / 10.0, m.G / 10.0,
                   78.5, 1.2e-05, 1.00, "Isotropic Linear Elastic", m.fy])

    # ---- 1.3 Cross-Sections [cm2 / cm4] ----------------------------------
    ws = wb.create_sheet("1.3 Cross-Sections")
    ws.append(["Section No.", "Description (RSTAB library)", "Matl. No.",
               "J [cm4]", "Iy [cm4] (major)", "Iz [cm4] (minor)", "A [cm2]",
               "app section", "comment"])
    secs = {s.name: s for s in model.sections.values()}
    sidx = {nm: i + 1 for i, nm in enumerate(secs)}
    for nm, s in secs.items():
        iy, iz = max(s.Iy, s.Iz), min(s.Iy, s.Iz)
        note = ("SHAPE-THIN: load/generate the section in RSTAB with this "
                "name; check the principal-axis rotation (uprights are "
                "typically rotated 180 deg)" if "SHAPE-THIN"
                in _rstab_section_name(nm) else "RSTAB parametric library")
        ws.append([sidx[nm], _rstab_section_name(nm), midx.get(s.material, 1),
                   s.J / 1.0e4, iy / 1.0e4, iz / 1.0e4, s.A / 1.0e2, nm, note])

    # ---- 1.3.2 Stiffness reduction (brace area factor) -------------------
    fac_by_sec = {}
    for m in _members_of(model):
        if m.area_factor and abs(m.area_factor - 1.0) > 1e-9:
            fac_by_sec[model.section_of(m).name] = m.area_factor
    if fac_by_sec:
        ws = wb.create_sheet("1.3.2 Stiffness Reduction")
        ws.append(["Section No.", "Description", "Factor J", "Factor Iy",
                   "Factor Iz", "Factor A", "Factor Ay", "Factor Az"])
        for nm, f in fac_by_sec.items():
            ws.append([sidx[nm], _rstab_section_name(nm),
                       1.00, 1.00, 1.00, f, 1.00, 1.00])

    # ---- 1.4 Member hinges [kNcm/rad] ------------------------------------
    hinges: list = []

    def hinge_no(h):
        if h is None:
            return ""
        key = (h.rx, h.ry, h.rz, getattr(h, "m_rd_z", None))
        for i, k in enumerate(hinges):
            if k[0] == key:
                return i + 1
        hinges.append((key, h))
        return len(hinges)

    mem_hinge = {m.id: (hinge_no(m.hinge_i), hinge_no(m.hinge_j))
                 for m in _members_of(model)}
    ws = wb.create_sheet("1.4 Member Hinges")
    ws.append(["Release No.", "Reference System",
               "ux [kN/cm]", "uy [kN/cm]", "uz [kN/cm]",
               "phi-x [kNcm/rad]", "phi-y [kNcm/rad]", "phi-z [kNcm/rad]",
               "comment"])
    for i, (key, h) in enumerate(hinges):
        def spring(v):
            return round(v / 1.0e4, 3) if isinstance(v, (int, float)) and v > 0 else ""
        ws.append([i + 1, "Local x,y,z", "", "", "",
                   spring(h.rx), spring(h.ry), spring(h.rz),
                   "beam-end connector (translations coupled)"])

    # ---- 1.7 Members ------------------------------------------------------
    ws = wb.create_sheet("1.7 Members")
    ws.append(["Member No.", "Member Type", "Start Node", "End Node",
               "Rotation Angle [deg]", "Cross-Section Start",
               "Cross-Section End", "Hinge Start", "Hinge End",
               "Length L [mm]"])
    for m in _members_of(model):
        sno = sidx.get(model.section_of(m).name, 1)
        hi, hj = mem_hinge[m.id]
        ws.append([m.id, "Truss" if m.mtype == "truss" else "Beam",
                   nmap[m.node_i], nmap[m.node_j], 0.00,
                   sno, sno, hi, hj, round(_member_length(model, m), 1)])

    # ---- 1.8 Nodal supports (+ 1.8.7 stiffness diagram) --------------------
    tbl = getattr(model, "base_axial_table", None)
    ws = wb.create_sheet("1.8 Nodal Supports")
    ws.append(["Support No.", "Nodes No.", "Rotation [deg]",
               "uX'", "uY'", "uZ'",
               "phi-X' [kNcm/rad]", "phi-Y' [kNcm/rad]", "phi-Z' [kNcm/rad]",
               "comment"])

    def dof(v):
        if v is True:
            return "fixed"
        if isinstance(v, (int, float)) and v > 0:
            return round(v / 1.0e4, 3)
        return "free"

    groups: dict = {}
    for sup in model.supports:
        key = (sup.ux, sup.uy, sup.uz, sup.rx,
               round(sup.ry, 3) if isinstance(sup.ry, float) else sup.ry,
               sup.rz)
        groups.setdefault(key, []).append(nmap[sup.node])
    for i, (key, nodes) in enumerate(groups.items()):
        ux, uy, uz, rx, ry, rz = key
        note = ("base plate - phi-Y' is the LINEAR spring; optionally "
                "upgrade to the axial-dependent diagram of sheet 1.8.7 "
                "(support nonlinearity 'Stiffness diagram' vs PZ')"
                if tbl else "base plate")
        ws.append([i + 1, _id_ranges(nodes), 0.00,
                   dof(ux), dof(uy), dof(uz),
                   dof(rx), dof(ry), dof(rz), note])
    if tbl:
        ws = wb.create_sheet("1.8.7 Support Stiffness Diagram")
        ws.append(["Support No.", "Degree of Freedom", "Dependent on Force",
                   "Force [kN]", "C [kNcm/rad]", "comment"])
        for j, (n_kn, k) in enumerate(tbl):
            ws.append([1, "phi-Y'", "PZ'+", float(n_kn), k / 1.0e4,
                       "" if j else "axial-dependent base stiffness"])
        ws.append([1, "phi-Y'", "PZ'+", f"> {tbl[-1][0]:.0f}",
                   tbl[-1][1] / 1.0e4, "Constant rigidity"])
        ws.append([1, "phi-Y'", "PZ'-", 0.0, 0.0, "Tearing (uplift)"])

    # ---- 1.11 Sets of members (continuous upright lines) -----------------
    sets: dict = {}
    for m in _members_of(model):
        lab = getattr(m, "set_label", None)
        if lab:
            sets.setdefault(lab.split(" · ")[0], []).append(m.id)
    set_no = {}
    ws = wb.create_sheet("1.11 Sets of Members")
    ws.append(["Set No.", "Description", "Type", "Member No.", "Length [mm]"])
    for i, (lab, mids) in enumerate(sorted(sets.items())):
        set_no[lab] = i + 1
        length = sum(_member_length(model, model.members[mid])
                     for mid in mids)
        ws.append([i + 1, lab, "Contin. member", _id_ranges(mids),
                   round(length, 1)])

    # ---- 2.1 Load cases + the two native imperfection LCs ------------------
    CAT = {"permanent": "Permanent", "variable": "Imposed",
           "placement": "Imposed", "other": "Imposed"}
    lc_no = {nm: i + 1 for i, nm in enumerate(model.load_cases)}
    LC_DESC = {"dead": "Dead Load (DL) - includes member self-weight",
               "pallets": "Level Load (LL)",
               "pallets_pattern": "Pattern Load (LL alternate levels)",
               "placement": "PL X at top level",
               "placement_lo": "PL X at highest level <= 3 m",
               "placement_y": "PL Y at frame top",
               "accidental_x": "AL X", "accidental_y": "AL Y"}
    phi_x = imp.value_for("+x") if imp else 1 / 300
    phi_y = imp.value_for("+y") if imp else 1 / 200
    imp_lc, imp_desc = {}, {}
    if any("x" in d for d in dirs):
        imp_lc["x"] = len(lc_no) + len(imp_lc) + 1
        imp_desc["x"] = f"Imperfection towards +X (L/{1 / phi_x:.0f})"
    if any("y" in d for d in dirs):
        imp_lc["y"] = len(lc_no) + len(imp_lc) + 1
        imp_desc["y"] = f"Imperfection towards +Y (L/{1 / phi_y:.0f})"
    ws = wb.create_sheet("2.1 Load Cases")
    ws.append(["Load Case", "Description", "Action Category",
               "Self-Weight Active", "SW Factor X", "SW Factor Y",
               "SW Factor Z", "Method of analysis"])
    for nm, lc in model.load_cases.items():
        cat = "Accidental" if nm.startswith("accidental") else \
            CAT.get(lc.case_type, "Imposed")
        ws.append([f"LC{lc_no[nm]}", LC_DESC.get(nm, nm), cat,
                   "No (self-weight is in the LC1 member loads)"
                   if nm == "dead" else "No", 0, 0, 0,
                   "Geometrically linear analysis"])
    for ax, no in imp_lc.items():
        ws.append([f"LC{no}", imp_desc[ax], "Imperfection", "No", 0, 0, 0,
                   "Geometrically linear analysis"])

    # ---- 2.5 load combinations (imp LC with factor +1 / -1) ---------------
    ws = wb.create_sheet("2.5 Load Combinations")
    ws.append(["Load Combin.", "DS", "Description", "No.", "Factor",
               "Load Case", "Load Case Description", "Method of analysis"])
    co = 0
    for row in _combo_rows(model):
        co += 1
        r = 0
        for key, f in row["factors"]:
            r += 1
            ws.append([f"CO{co}" if r == 1 else "",
                       row["ds"] if r == 1 else "",
                       row["name"] if r == 1 else "", r, f,
                       f"LC{lc_no[key]}", LC_DESC.get(key, key),
                       row["method"] if r == 1 else ""])
        d = row["imp"]
        if d:
            r += 1
            ax = "x" if "x" in d else "y"
            sgn = 1.0 if d[0] == "+" else -1.0
            ws.append(["", "", "", r, sgn, f"LC{imp_lc[ax]}", imp_desc[ax],
                       ""])

    # ---- 3.1 / 3.2 loads ---------------------------------------------------
    ws = wb.create_sheet("3.1 Nodal Loads")
    ws.append(["Load Case", "Nodes No.", "FX [kN]", "FY [kN]", "FZ [kN]",
               "comment"])
    for nm, lc in model.load_cases.items():
        for nl in lc.nodal_loads:
            ws.append([f"LC{lc_no[nm]}", nmap[nl.node],
                       round(nl.fx / 1e3, 4), round(nl.fy / 1e3, 4),
                       round(-nl.fz / 1e3, 4), LC_DESC.get(nm, nm)])
    ws = wb.create_sheet("3.2 Member Loads")
    ws.append(["Load Case", "Members No.", "Load Type", "Load Distribution",
               "Load Direction", "p [kN/m]", "comment"])
    for nm, lc in model.load_cases.items():
        byq: dict = {}
        for ml in lc.member_loads:
            if abs(ml.qz) > 1e-12:
                byq.setdefault(round(-ml.qz, 6), []).append(ml.member)
        for q, mids in sorted(byq.items()):
            ws.append([f"LC{lc_no[nm]}", _id_ranges(mids), "Force",
                       "Uniform", "ZL (global Z, down +)", q,
                       LC_DESC.get(nm, nm)])

    # ---- 3.4 imperfections: the inclination data of the two imp LCs -------
    if imp_lc:
        ws = wb.create_sheet("3.4 Imperfections")
        ws.append(["Load Case", "Reference to", "On Members No. (sets)",
                   "Dir.", "Inclination 1/phi [-]", "Precamber", "comment"])
        all_sets = _id_ranges(set_no.values())
        if "x" in imp_lc:
            ws.append([f"LC{imp_lc['x']}", "Set of members", all_sets, "z",
                       round(1 / phi_x, 2), 0.0,
                       "down-aisle sway imperfection (+X; COs use factor "
                       "-1 for -X)"])
        if "y" in imp_lc:
            ws.append([f"LC{imp_lc['y']}", "Set of members", all_sets, "y",
                       round(1 / phi_y, 2), 0.0,
                       "cross-aisle sway imperfection (+Y; COs use factor "
                       "-1 for -Y)"])

    # ---- import notes ------------------------------------------------------
    ws = wb.create_sheet("IMPORT NOTES")
    for line in [
        "RSTAB 8 import: File > Import > Microsoft Excel, tick 'Import",
        "worksheets to tables'; sheet names / columns follow the RSTAB 8",
        "data tables.  Units: mm, kN, kN/cm2, cm4, kNcm/rad, kN/m.",
        "Axes: RSTAB global Z points DOWN - node Z and load FZ are already",
        "converted (app is Z-up); X = down-aisle, Y = cross-aisle.",
        "",
        "1) Imperfections: TWO native load cases exactly like an RSTAB-",
        "   authored model - Imp X (inclination 1/300) and Imp Y (1/200)",
        "   on the continuous upright member sets of sheet 1.11 (data on",
        "   sheet 3.4).  Combinations reference them with factor +1; the",
        "   minus-direction combinations use factor -1 (flip the",
        "   inclination sign in a mirrored load case if your RSTAB",
        "   version rejects negative imperfection factors).",
        "2) Cross-sections: RRO-PAR names come from the RSTAB parametric",
        "   library; SHAPE-THIN sections must exist in the section database",
        "   under the given name (or assign your equivalents).  Reference",
        "   A/Iy/Iz/J values from the app are on sheet 1.3.",
        "3) Member hinges: linear rotational springs phi-z [kNcm/rad] -",
        "   the beam-end connector values.",
        "4) Nodal supports: translations fixed; phi-Y' (down-aisle rocking)",
        "   carries the LINEAR base spring so the import runs directly;",
        "   optionally upgrade it to the axial-dependent stiffness diagram",
        "   of sheet 1.8.7 (support nonlinearity vs PZ' with tearing).",
        "5) Load cases: self-weight factors are 0 because LC1 (dead)",
        "   already carries every member self-weight as member loads -",
        "   do NOT additionally activate RSTAB self-weight.",
        "6) Combinations: ULS/ACC run 'Second order analysis (P-Delta)',",
        "   SLS geometrically linear - set in Calculation Parameters;",
        "   stiffness NOT reduced by gamma_M (Partial Factor 1.00).",
        "7) Brace area factor (X/D bracing tension model) is on sheet",
        "   1.3.2 as an RSTAB cross-section stiffness reduction Factor A.",
    ]:
        ws.append([line])
    wb.save(path)
    return path
