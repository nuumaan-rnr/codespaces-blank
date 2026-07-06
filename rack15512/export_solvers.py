"""Export a RackModel to neutral solver input files so a project can be re-run
in RSTAB/RFEM or STAAD.Pro instead of (or to cross-check) the OpenSeesPy engine.

ADDITIVE only - reads a RackModel, writes input decks; no engine changes.

  * to_staad(model, path)      -> STAAD.Pro .std text input
  * to_rstab_xlsx(model, path) -> RSTAB/RFEM table .xlsx (Nodes/Members/Sections/
                                  Materials/Supports/Hinges/Loads), the same
                                  tabular layout RSTAB imports from Excel.

Axis convention: this app uses Z up (gravity = -Z).  STAAD.Pro SPACE uses Y up,
so coordinates are mapped (X, Y, Z)_staad = (X, Z, Y)_app and gravity is -Y.
RSTAB keeps the app's axes (Z up); loads are written with gravity in -Z.

Both decks carry the geometry, sections (as prismatic A/I/J), materials, the
nodal supports (with rotational spring constants), the beam-end connector hinges
(rotational springs), and the characteristic pallet + dead load case.  Load
combinations, imperfections and the 2nd-order setting are emitted as comments /
a note so the engineer applies the same EN 15512 combinations in the target
solver (they differ per code and are documented in the report).
"""

from __future__ import annotations

import math
from typing import Dict, List

from .model import RackModel


def _members_of(model: RackModel):
    return sorted(model.members.values(), key=lambda m: m.id)


def _node_map(model: RackModel) -> Dict[int, int]:
    """1-based node id remap (STAAD/RSTAB joints must be >= 1; app uses 0-based)."""
    return {nid: i + 1 for i, nid in enumerate(sorted(model.nodes))}


def _udl_load_case(model: RackModel):
    """Collect the characteristic gravity member UDLs [N/mm] (down = -Z) from the
    'pallets' + 'dead' load cases if present, keyed by member id."""
    q: Dict[int, float] = {}
    for lc in model.load_cases.values():
        if lc.name not in ("pallets", "dead"):
            continue       # skip pattern/placement/accidental variants
        for ml in getattr(lc, "member_loads", []):
            q[ml.member] = q.get(ml.member, 0.0) + getattr(ml, "qz", 0.0)
    return q


# ----------------------------------------------------------------- STAAD .std
def to_staad(model: RackModel, path: str) -> str:
    """Write a STAAD.Pro .std input deck (mm, N).  Returns the path."""
    L: List[str] = []
    L.append("STAAD SPACE")
    L.append("START JOB INFORMATION")
    L.append(f"ENGINEER DATE {model.name}")
    L.append("END JOB INFORMATION")
    L.append("* Exported from Racks & Rollers (EN 15512 app). App axes: Z up.")
    L.append("* STAAD SPACE uses Y up -> coords mapped (x,y,z)=(X,Z,Y); gravity=-Y.")
    L.append("UNIT MMS NEWTON")
    nmap = _node_map(model)

    # joints (Y up): staad_y = app_z, staad_z = app_y
    L.append("JOINT COORDINATES")
    for n in sorted(model.nodes.values(), key=lambda n: n.id):
        L.append(f"{nmap[n.id]} {n.x:.4f} {n.z:.4f} {n.y:.4f};")

    L.append("MEMBER INCIDENCES")
    for m in _members_of(model):
        L.append(f"{m.id} {nmap[m.node_i]} {nmap[m.node_j]};")

    # materials (one Steel per distinct E/G)
    L.append("DEFINE MATERIAL START")
    done = set()
    for mat in model.materials.values():
        nm = mat.name.replace(" ", "_")
        if nm in done:
            continue
        done.add(nm)
        L.append(f"ISOTROPIC {nm}")
        L.append(f"E {mat.E}")
        L.append(f"POISSON {getattr(mat, 'nu', 0.3)}")
        L.append("DENSITY 7.85e-08")
        L.append(f"G {mat.G}")
    L.append("END DEFINE MATERIAL")

    # prismatic section per member (AX/IX/IY/IZ in mm)
    L.append("MEMBER PROPERTY AMERICAN")
    for m in _members_of(model):
        s = model.section_of(m)
        a = s.A * m.area_factor
        L.append(f"{m.id} PRIS AX {a:.3f} IX {s.J:.1f} IY {s.Iy:.1f} IZ {s.Iz:.1f}")

    # material assignment per member
    L.append("CONSTANTS")
    for m in _members_of(model):
        nm = model.material_of(m).name.replace(" ", "_")
        L.append(f"MATERIAL {nm} MEMB {m.id}")

    # supports (translations fixed; rotational springs from support.ry etc.)
    L.append("SUPPORTS")
    for sup in model.supports:
        parts = [f"{sup.node}"]
        # STAAD FIXED BUT releases free DOFs; spring via KFX.. KMX..; map app
        # (ux,uy,uz,rx,ry,rz) -> staad (FX,FZ?,FY,..). Keep translations fixed.
        # Use a generic: translations fixed, rotational springs where given.
        kmx = sup.ry if isinstance(sup.ry, (int, float)) else 0.0   # app ry = down-aisle
        # STAAD: FIXED BUT MX MY MZ <springs>; we fix translations, spring rotations
        spr = []
        # app ry (about global Y / down-aisle bending) -> STAAD MY (about staad Y=app Z)?
        # Map app rotational DOFs to STAAD: app rx->MX, app ry->MZ(staad), app rz->MY
        def kk(v):
            return v if isinstance(v, (int, float)) and v > 0 else None
        rx, ry, rz = kk(sup.rx), kk(sup.ry), kk(sup.rz)
        rel = []
        if rx is None: rel.append("MX")
        else: spr.append(f"KMX {rx:.0f}")
        # app ry (down-aisle, about app Y) -> STAAD MZ (about staad Z = app Y)
        if ry is None: rel.append("MZ")
        else: spr.append(f"KMZ {ry:.0f}")
        if rz is None: rel.append("MY")
        else: spr.append(f"KMY {rz:.0f}")
        line = f"{nmap[sup.node]} FIXED BUT " + " ".join(rel + spr)
        L.append(line.strip())

    # beam-end connector hinges: partial moment release with rotational spring
    # (app hinge.rz about member local z = beam strong axis -> STAAD MZ)
    rel_lines = []
    for m in _members_of(model):
        for end, h in (("START", m.hinge_i), ("END", m.hinge_j)):
            if h is None:
                continue
            kz = getattr(h, "rz", None)
            if kz and kz > 0:
                rel_lines.append(f"{m.id} {end} KMZ {kz:.0f}")
            elif kz == 0:
                rel_lines.append(f"{m.id} {end} MZ")
    if rel_lines:
        L.append("MEMBER RELEASE")
        L.extend(rel_lines)

    # characteristic gravity load case (pallets+dead) as member UDL in -Y (staad)
    q = _udl_load_case(model)
    L.append("LOAD 1 LOADTYPE LIVE  TITLE PALLET + DEAD (characteristic)")
    L.append("MEMBER LOAD")
    for mid, qz in q.items():
        if abs(qz) > 1e-9:
            # app qz [N/mm] downward (-Z) -> STAAD GY (global Y up) negative
            L.append(f"{mid} UNI GY {qz:.5f}")
    L.append("LOAD 2 LOADTYPE DEAD  TITLE SELFWEIGHT")
    L.append("SELFWEIGHT Y -1.0")
    L.append("* EN 15512 ULS combos (apply in STAAD): 1.3 DL + 1.4 LL (+ placement),")
    L.append("* plus a sway imperfection and a 2nd-order (P-Delta) analysis:")
    L.append("LOAD COMB 101 1.3DL + 1.4LL")
    L.append("1 1.4 2 1.3")
    L.append("PERFORM ANALYSIS PRINT STATICS CHECK")
    L.append("* For 2nd order use:  PERFORM ANALYSIS  with  DEFINE PDELTA / PDELTA")
    L.append("FINISH")

    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(L) + "\n")
    return path


# --------------------------------------------------------------- RSTAB .xlsx
def to_rstab_xlsx(model: RackModel, path: str) -> str:
    """Write an RSTAB/RFEM table workbook (Nodes/Materials/Cross-Sections/
    Members/Nodal Supports/Member Hinges/Load Case) for Excel import."""
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
    # collect distinct hinges
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
        ["Axes: Z up, gravity -Z (RSTAB default global Z can be set down)."],
        ["Cross-sections are prismatic A/Iy/Iz/J; assign the real SHAPE-THIN /"],
        ["RRO sections in RSTAB if available for exact warping/shear."],
        ["Apply EN 15512 ULS combos (1.3DL+1.4LL+..), sway imperfection and a"],
        ["2nd-order (P-Delta) analysis in RSTAB to reproduce the app's checks."],
    ]:
        ws.append(row)

    wb.save(path)
    return path


def export_project(model_json: str, out_dir: str, name: str = "model") -> dict:
    """Load a saved project model.json and write both solver decks."""
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
#   1.1 Nodes [mm, global Z DOWN]          1.8 Nodal Supports
#   1.2 Materials [kN/cm2]                 1.8.7 Support stiffness diagram
#   1.3 Cross-Sections [cm2, cm4]          1.11 Sets of Members
#   1.3.2 Stiffness reduction (braces)     2.1 Load Cases (+ imperfection LCs)
#   1.4 Member Hinges [kNcm/rad]           2.5 Load Combinations
#   1.7 Members                            3.1/3.2 Loads [kN, kN/m]
#                                          3.4 Imperfections (on member sets)
_RSTAB_SECTION_MAP = {
    # app section name -> RSTAB library / SHAPE-THIN description
    "1C36X21X1.2": "SHAPE-THIN B5H36X21T012",
}


def _rstab_section_name(name: str) -> str:
    """RSTAB description for an app section: known mappings, RRO-PAR for
    cold-formed RHS names (RHS<h>X<b>X<t>), SHAPE-THIN <name> otherwise."""
    import re
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


def to_rstab8_xlsx(model: RackModel, path: str) -> str:
    """Write an RSTAB 8 table workbook of the whole model - geometry,
    materials, cross-sections (RSTAB library names), member hinges, supports
    (incl. the axial-dependent base stiffness diagram), sets of members,
    load cases with the sway-imperfection cases, every load and the app's
    generated load combinations - so the model can be recreated in RSTAB via
    File > Import > Microsoft Excel and run directly.  Returns the path."""
    import openpyxl
    wb = openpyxl.Workbook()
    nmap = _node_map(model)

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
    import math as _math
    for m in _members_of(model):
        ni, nj = model.nodes[m.node_i], model.nodes[m.node_j]
        L = _math.dist((ni.x, ni.y, ni.z), (nj.x, nj.y, nj.z))
        sno = sidx.get(model.section_of(m).name, 1)
        hi, hj = mem_hinge[m.id]
        ws.append([m.id, "Truss" if m.mtype == "truss" else "Beam",
                   nmap[m.node_i], nmap[m.node_j], 0.00,
                   sno, sno, hi, hj, round(L, 1)])

    # ---- 1.8 Nodal supports (+ 1.8.7 stiffness diagram) --------------------
    tbl = getattr(model, "base_axial_table", None)
    ws = wb.create_sheet("1.8 Nodal Supports")
    ws.append(["Support No.", "Nodes No.", "Rotation [deg]",
               "uX'", "uY'", "uZ'",
               "phi-X' [kNcm/rad]", "phi-Y' [kNcm/rad]", "phi-Z' [kNcm/rad]",
               "comment"])

    def dof(v, diagram=False):
        if diagram:
            return "Stiffness Diagram"
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
        ws.append([i + 1, _id_ranges(nodes), 0.00,
                   dof(ux), dof(uy), dof(uz),
                   dof(rx), dof(ry, diagram=bool(tbl)), dof(rz),
                   "base plate; phi-Y' nonlinear vs axial force (sheet "
                   "1.8.7)" if tbl else "base plate"])
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
        length = sum(
            _math.dist((model.nodes[model.members[mid].node_i].x,
                        model.nodes[model.members[mid].node_i].y,
                        model.nodes[model.members[mid].node_i].z),
                       (model.nodes[model.members[mid].node_j].x,
                        model.nodes[model.members[mid].node_j].y,
                        model.nodes[model.members[mid].node_j].z))
            for mid in mids)
        ws.append([i + 1, lab, "Contin. member", _id_ranges(mids),
                   round(length, 1)])

    # ---- 2.1 Load cases (+ imperfection LCs) ------------------------------
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
    imp = model.imperfection
    imp_dirs: list = []
    for c in model.combinations:
        for d in (c.imp_directions or (imp.directions if imp else [])):
            if c.imperfection and d not in imp_dirs:
                imp_dirs.append(d)
    imp_lc = {}
    for d in imp_dirs:
        imp_lc[d] = len(lc_no) + len(imp_lc) + 1
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
    for d, no in imp_lc.items():
        phi = (imp.phi_s if "x" in d else imp.phi_s_cross) if imp else 1 / 300
        ws.append([f"LC{no}",
                   f"Imperfection towards {d[0]} {d[1].upper()} "
                   f"(L/{1 / phi:.0f})", "Imperfection", "No", 0, 0, 0,
                   "Geometrically linear analysis"])

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

    # ---- 3.4 imperfections (on the upright member sets) -------------------
    if imp_lc:
        ws = wb.create_sheet("3.4 Imperfections")
        ws.append(["Load Case", "Reference to", "On Members No. (sets)",
                   "Direction", "Inclination 1/phi [-]", "Precamber",
                   "comment"])
        all_sets = _id_ranges(set_no.values())
        for d, no in imp_lc.items():
            phi = (imp.phi_s if "x" in d else imp.phi_s_cross) if imp else 1 / 300
            sign = 1.0 if d[0] == "+" else -1.0
            ws.append([f"LC{no}", "Set of members", all_sets,
                       "z" if "x" in d else "y",
                       round(sign / phi, 2), 0.0,
                       f"sway imperfection {d} (uniform, all upright lines)"])

    # ---- 2.5 load combinations --------------------------------------------
    ws = wb.create_sheet("2.5 Load Combinations")
    ws.append(["Load Combin.", "DS", "Description", "No.", "Factor",
               "Load Case", "Load Case Description", "Method of analysis"])
    co = 0
    for c in model.combinations:
        dirs = c.imp_directions if (c.imperfection and imp) else [None]
        if c.imperfection and not c.imp_directions and imp:
            dirs = imp.directions
        for d in dirs:
            co += 1
            ds = ("ACC" if any(k.startswith("accidental") for k in c.factors)
                  else c.kind)
            desc = c.name + (f" (imp {d})" if d else "")
            method = ("Second order analysis (P-Delta)" if c.kind == "ULS"
                      else "Geometrically linear analysis")
            row = 0
            for lcn, f in c.factors.items():
                row += 1
                ws.append([f"CO{co}" if row == 1 else "", ds if row == 1 else "",
                           desc if row == 1 else "", row, f,
                           f"LC{lc_no[lcn]}", LC_DESC.get(lcn, lcn),
                           method if row == 1 else ""])
            if d:
                row += 1
                ws.append(["", "", "", row, 1.00, f"LC{imp_lc[d]}",
                           f"Imperfection {d}", ""])

    # ---- import notes ------------------------------------------------------
    ws = wb.create_sheet("IMPORT NOTES")
    for line in [
        "RSTAB 8 import: File > Import > Microsoft Excel, tick 'Import",
        "worksheets to tables'; sheet names / columns follow the RSTAB 8",
        "data tables.  Units: mm, kN, kN/cm2, cm4, kNcm/rad, kN/m.",
        "Axes: RSTAB global Z points DOWN - node Z and load FZ are already",
        "converted (app is Z-up); X = down-aisle, Y = cross-aisle.",
        "",
        "1) Cross-sections: RRO-PAR names come from the RSTAB parametric",
        "   library; SHAPE-THIN sections must exist in the section database",
        "   under the given name (or assign your equivalents).  Reference",
        "   A/Iy/Iz/J values from the app are on sheet 1.3.",
        "2) Member hinges: linear rotational springs phi-z [kNcm/rad] -",
        "   the beam-end connector values.",
        "3) Nodal supports: translations fixed; phi-Y' (down-aisle rocking)",
        "   uses the axial-dependent stiffness diagram on sheet 1.8.7 -",
        "   enter it as a support nonlinearity 'Stiffness diagram depending",
        "   on PZ'; the Excel import cannot carry nonlinearities.",
        "4) Load cases: self-weight factors are 0 because LC1 (dead)",
        "   already carries every member self-weight as member loads -",
        "   do NOT additionally activate RSTAB self-weight.",
        "5) Imperfection LCs: apply as RSTAB imperfections (inclination",
        "   1/300 down-aisle, 1/200 cross-aisle) on the continuous upright",
        "   member sets of sheet 1.11, direction per LC description.",
        "6) Combinations: ULS/ACC run 'Second order analysis (P-Delta)',",
        "   SLS geometrically linear - set in Calculation Parameters;",
        "   stiffness NOT reduced by gamma_M (Partial Factor 1.00).",
        "7) Brace area factor (X/D bracing tension model) is on sheet",
        "   1.3.2 as an RSTAB cross-section stiffness reduction Factor A.",
    ]:
        ws.append([line])
    wb.save(path)
    return path
