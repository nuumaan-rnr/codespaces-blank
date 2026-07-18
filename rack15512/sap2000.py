"""Importer / exporter for SAP2000 model workbooks (the CSi Database Tables
Excel export, sheets 'Joint Coordinates', 'Connectivity - Frame',
'Frame Section Assignments', 'Frame Props 01 - General', 'MatProp 02 - Basic
Mech Props', 'MatProp 03a - Steel Data', 'Frame Releases 1/2', 'Joint
Restraint Assignments', 'Joint/Frame Loads', 'Load Pattern/Case Definitions',
'Combination Definitions', 'Frame Property Modifiers').

Conventions handled
-------------------
* SAP2000 is Z-up and uses N-mm (the workbook states units per column); this
  app is Z-up N-mm too, so coordinates and forces import 1:1.
* Section properties are taken AS COMPUTED BY SAP (Frame Props 01: Area, I33,
  I22, J, section moduli, shear areas) - no re-derivation from a library, so
  the imported model uses exactly SAP's stiffness.  SAP local axis 3 (major
  bending) -> this app's local z; axis 2 -> local y.
* Frame property modifiers: SAP's EA/EI modifiers scale E*A and E*I, so the
  material E is scaled by the (single, uniform) EI modifier on import.
* Member end releases: SAP M3 (major moment) -> this app's rz, M2 -> ry, T ->
  rx.  A released DOF with a partial-fixity spring becomes that spring value
  [N*mm/rad]; released with no spring is a pin (0.0); not released is
  continuous (None).
* Notional / sway load patterns (e.g. SWAY_X) are ordinary load cases here -
  SAP models the sway imperfection as explicit horizontal joint forces, which
  is exactly this app's EHF, so no separate imperfection object is needed.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .model import (Combination, CrossSection, Hinge, LoadCase, MemberLoad,
                    NodalLoad, RackModel, Steel, Support)


# --------------------------------------------------------------- sheet helpers
def _load(path):
    """Open one workbook or several (a SAP export is often split across files);
    returns a list of workbooks so a table can be found in whichever holds it."""
    import openpyxl
    paths = [path] if isinstance(path, (str, bytes)) else list(path)
    return [openpyxl.load_workbook(p, data_only=True, read_only=True)
            for p in paths]


def _sheet_rows(wbs, name: str):
    for wb in wbs:
        for sheet in wb.sheetnames:
            if sheet.strip() == name or sheet.strip().startswith(name):
                return list(wb[sheet].iter_rows(values_only=True))
    return None


def _table(wbs, name: str) -> Tuple[List[str], List[dict]]:
    """Return (header, [row-dict]) for a SAP table sheet, searching every open
    workbook.  Row 1 is the 'TABLE: ...' title, row 2 the column names, row 3
    the units, data from row 4."""
    rows = _sheet_rows(wbs, name)
    if not rows or len(rows) < 2:
        return [], []
    hdr = [("" if c is None else str(c).strip()) for c in rows[1]]
    out = []
    for r in rows[3:]:
        if r is None or r[0] in (None, ""):
            continue
        out.append({hdr[i]: r[i] for i in range(min(len(hdr), len(r)))})
    return hdr, out


def _f(v, d=None):
    if v is None or v == "":
        return d
    try:
        return float(v)
    except (TypeError, ValueError):
        return d


def _yes(v) -> bool:
    return str(v).strip().lower() in ("yes", "true", "1")


# ---------------------------------------------------------------- import
_ROLE_BY_SHAPE = {"box/tube": "pallet beams", "sd section": "uprights",
                  "channel": "bracing", "angle": "bracing",
                  "i/wide flange": "pallet beams", "plate": "bracing"}


def load_sap2000(path: str) -> RackModel:
    """Build a RackModel from a SAP2000 database-tables workbook, using SAP's
    own section properties and stiffness modifiers."""
    wb = _load(path)
    model = RackModel(name="SAP2000 import")

    # ---- materials (E, G, fy, unit weight) --------------------------------
    _, mech = _table(wb, "MatProp 02 - Basic Mech Props")
    _, steel = _table(wb, "MatProp 03a - Steel Data")
    fy_of = {r["Material"]: _f(r.get("Fy"), 250.0) for r in steel}
    gamma: Dict[str, float] = {}
    for r in mech:
        name = r["Material"]
        E = _f(r.get("E1"), 210000.0)
        G = _f(r.get("G12")) or (E / (2 * (1 + 0.3)))
        model.materials[name] = Steel(name, E=E, G=G,
                                      fy=fy_of.get(name, 250.0))
        gamma[name] = _f(r.get("UnitWeight"), 7.7e-5)   # N/mm^3

    # ---- stiffness modifier (uniform EI/EA factor -> scale E) -------------
    _, mods = _table(wb, "Frame Property Modifiers")
    ei = {_f(r.get("EIModifier"), 1.0) for r in mods}
    ea = {_f(r.get("EAModifier"), 1.0) for r in mods}
    stiff_factor = 1.0
    if len(ei) == 1 and len(ea) == 1:
        f_ei = next(iter(ei))
        if abs(f_ei - next(iter(ea))) < 1e-9 and f_ei not in (None, 0):
            stiff_factor = f_ei
    if stiff_factor != 1.0:                     # fold into every material's E
        for mat in model.materials.values():
            mat.E *= stiff_factor
            mat.G *= stiff_factor
    model.notes = (f"SAP2000 import; E*A and E*I scaled by {stiff_factor:g} "
                   "(SAP frame property modifiers)")

    # ---- cross-sections (SAP's own properties; axis 3->z, 2->y) -----------
    _, props = _table(wb, "Frame Props 01 - General")
    shape_of: Dict[str, str] = {}
    for r in props:
        name = r["SectionName"]
        A = _f(r.get("Area"), 1.0)
        I33 = _f(r.get("I33"), 1.0)             # major -> local z
        I22 = _f(r.get("I22"), 1.0)             # minor -> local y
        S33 = _f(r.get("S33Top")) or _f(r.get("S33Bot"))
        S22 = _f(r.get("S22Left")) or _f(r.get("S22Right"))
        t3 = _f(r.get("t3"))
        t2 = _f(r.get("t2"))
        mat = r.get("Material")
        model.sections[name] = CrossSection(
            name=name, material=mat if mat in model.materials
            else next(iter(model.materials), "S235"),
            A=A, Iy=I22, Iz=I33, J=max(_f(r.get("TorsConst"), 1.0), 1.0),
            Wely=S22 or (I22 / (t2 / 2.0) if t2 else I22 / 25.0),
            Welz=S33 or (I33 / (t3 / 2.0) if t3 else I33 / 50.0),
            width_b=t2, depth_h=t3, role=_ROLE_BY_SHAPE.get(
                str(r.get("Shape")).lower(), ""),
            description=f"SAP2000 {r.get('Shape')} section (I33/I22 as SAP)")
        shape_of[name] = str(r.get("Shape")).lower()

    # ---- nodes -------------------------------------------------------------
    _, joints = _table(wb, "Joint Coordinates")
    for r in joints:
        jid = int(float(r["Joint"]))
        model.add_node(jid, _f(r.get("GlobalX"), _f(r.get("XorR"), 0.0)),
                       _f(r.get("GlobalY"), _f(r.get("Y"), 0.0)),
                       _f(r.get("GlobalZ"), _f(r.get("Z"), 0.0)))

    # ---- member end releases ----------------------------------------------
    _, rel1 = _table(wb, "Frame Releases 1 - General")
    _, rel2 = _table(wb, "Frame Releases 2 - Part Fixity")
    fixity = {str(r["Frame"]): r for r in rel2}

    def _hinge(rel, side: str) -> Optional[Hinge]:
        m3 = _yes(rel.get(f"M3{side}"))         # major -> rz
        m2 = _yes(rel.get(f"M2{side}"))         # minor -> ry
        tt = _yes(rel.get(f"T{side}"))          # torsion -> rx
        if not (m3 or m2 or tt):
            return None
        fx = fixity.get(str(rel["Frame"]), {})

        def spr(flag, key):
            if not flag:
                return None
            v = _f(fx.get(key))
            return v if v and v > 0 else 0.0
        return Hinge(rz=spr(m3, f"M3{side}"), ry=spr(m2, f"M2{side}"),
                     rx=spr(tt, f"T{side}"))
    releases = {}
    for rel in rel1:
        releases[str(rel["Frame"])] = (_hinge(rel, "I"), _hinge(rel, "J"))

    # ---- members -----------------------------------------------------------
    _, conn = _table(wb, "Connectivity - Frame")
    _, assign = _table(wb, "Frame Section Assignments")
    _, laxes = _table(wb, "Frame Local Axes 1 - Typical")
    angle_of = {str(r["Frame"]): _f(r.get("Angle"), 0.0) for r in laxes}
    sec_of = {str(r["Frame"]): (r.get("AnalSect") or r.get("DesignSect"))
              for r in assign}

    def _vecxz(ni: int, nj: int, angle: float):
        """SAP local-axis angle -> this app's vecxz.  A 90/270 deg angle (mod
        180) swaps the two transverse axes (SAP's I33/I22 then act in the
        opposite planes to this app's default), so the section's Iz/Iy land in
        the correct global planes.  Only the +-90 deg swap is handled (the
        common rack upright rotation); other angles keep the default axes."""
        import math
        a = model.nodes[ni]
        b = model.nodes[nj]
        dx, dy, dz = b.x - a.x, b.y - a.y, b.z - a.z
        L = math.sqrt(dx * dx + dy * dy + dz * dz) or 1.0
        swap = abs(((angle or 0.0) % 180.0) - 90.0) < 45.0
        if not swap:
            return None                       # default orientation
        if abs(dz / L) > 0.999:               # vertical member: swap y<->z
            return (1.0, 0.0, 0.0)
        # horizontal/inclined member rotated 90 deg: local z becomes vertical
        return (0.0, 0.0, 1.0)

    for r in conn:
        fid = int(float(r["Frame"]))
        sec = sec_of.get(str(r["Frame"]))
        if sec not in model.sections:
            continue
        role = model.sections[sec].role
        mtype = "truss" if role == "bracing" else "beam"
        hi, hj = releases.get(str(r["Frame"]), (None, None))
        ni, nj = int(float(r["JointI"])), int(float(r["JointJ"]))
        model.add_member(fid, ni, nj, sec, mtype=mtype,
                         hinge_i=hi if mtype == "beam" else None,
                         hinge_j=hj if mtype == "beam" else None,
                         mesh=2 if mtype == "beam" else 1,
                         member_set=role or sec,
                         vecxz=_vecxz(ni, nj, angle_of.get(str(r["Frame"]),
                                                           0.0)))

    # ---- supports (restraints + uncoupled springs) ------------------------
    _, restr = _table(wb, "Joint Restraint Assignments")
    _, springs = _table(wb, "Jt Spring Assigns 1 - Uncoupled")
    spr_of = {int(float(r["Joint"])): r for r in springs}

    def _dof(fixed, spring):
        if fixed:
            return True
        return spring if (spring and spring > 0) else False
    for r in restr:
        nid = int(float(r["Joint"]))
        if nid not in model.nodes:
            continue
        sp = spr_of.get(nid, {})
        model.supports.append(Support(
            nid,
            ux=_dof(_yes(r.get("U1")), _f(sp.get("U1"))),
            uy=_dof(_yes(r.get("U2")), _f(sp.get("U2"))),
            uz=_dof(_yes(r.get("U3")), _f(sp.get("U3"))),
            rx=_dof(_yes(r.get("R1")), _f(sp.get("R1"))),
            ry=_dof(_yes(r.get("R2")), _f(sp.get("R2"))),
            rz=_dof(_yes(r.get("R3")), _f(sp.get("R3")))))

    # ---- auto-mesh at joints BEFORE loads, so self-weight and distributed
    #      loads land on every sub-member (SAP splits each frame at joints on
    #      its span; without this the split-off segments carry no load) -------
    model.frame_origin = {mid: mid for mid in model.members}
    _automesh_at_joints(model)
    subs_of: Dict[int, List[int]] = {}          # SAP frame -> sub-member ids
    for mid, fr in model.frame_origin.items():
        subs_of.setdefault(fr, []).append(mid)

    # ---- load patterns / cases --------------------------------------------
    _, pats = _table(wb, "Load Pattern Definitions")
    selfwt = {r["LoadPat"]: _f(r.get("SelfWtMult"), 0.0) for r in pats}
    cases: Dict[str, LoadCase] = {}
    for name in selfwt:
        kind = "permanent" if str(name).upper().startswith("DEAD") \
            else "variable"
        cases[name] = LoadCase(name, kind)

    # self-weight member UDLs on every (meshed) member
    for name, mult in selfwt.items():
        if not mult:
            continue
        for m in model.members.values():
            sec = model.sections[m.section]
            g = gamma.get(sec.material, 7.7e-5)
            w = sec.A * g * mult                 # N/mm
            cases[name].member_loads.append(MemberLoad(m.id, qz=-w))

    # distributed frame loads (gravity) -> apply to every sub-member of the frame
    _, dist = _table(wb, "Frame Loads - Distributed")
    for r in dist:
        pat = r.get("LoadPat")
        if pat not in cases:
            cases[pat] = LoadCase(pat, "variable")
        fid = int(float(r["Frame"]))
        w = _f(r.get("FOverLA"), 0.0)
        d = str(r.get("Dir", "Gravity")).lower()
        for sub in subs_of.get(fid, [fid] if fid in model.members else []):
            ml = MemberLoad(sub)
            if "grav" in d or d in ("z", "-z", "3"):
                ml.qz = -abs(w)
            elif d in ("x", "1"):
                ml.qx = w
            elif d in ("y", "2"):
                ml.qy = w
            else:
                ml.qz = -abs(w)
            cases[pat].member_loads.append(ml)

    # joint force loads (notional / sway)
    _, jl = _table(wb, "Joint Loads - Force")
    for r in jl:
        pat = r.get("LoadPat")
        if pat not in cases:
            cases[pat] = LoadCase(pat, "variable")
        nid = int(float(r["Joint"]))
        if nid not in model.nodes:
            continue
        cases[pat].nodal_loads.append(NodalLoad(
            nid, fx=_f(r.get("F1"), 0.0), fy=_f(r.get("F2"), 0.0),
            fz=_f(r.get("F3"), 0.0), mx=_f(r.get("M1"), 0.0),
            my=_f(r.get("M2"), 0.0), mz=_f(r.get("M3"), 0.0)))

    for name, lc in cases.items():
        model.load_cases[name] = lc

    # ---- combinations ------------------------------------------------------
    _, combos = _table(wb, "Combination Definitions")
    factors: Dict[str, Dict[str, float]] = {}
    order: List[str] = []
    for r in combos:
        name = r.get("ComboName")
        case = r.get("CaseName")
        sf = _f(r.get("ScaleFactor"), 1.0)
        if not name or not case:
            continue
        if name not in factors:
            factors[name] = {}
            order.append(name)
        if case in model.load_cases:            # skip modal/spectrum refs
            factors[name][case] = factors[name].get(case, 0.0) + sf
    for name in order:
        fac = factors[name]
        if not fac:
            continue
        kind = "SLS" if str(name).upper().startswith("SLS") else "ULS"
        # SAP combinations are a Linear Add of linear-static cases, so run them
        # geometrically LINEAR to match SAP's LinStatic output (a P-Delta case
        # is a separate SAP load case, not the combination).
        model.combinations.append(Combination(
            name, kind, fac, imperfection=False, order=1))

    return model


def _automesh_at_joints(model: RackModel, tol: float = 2.0) -> int:
    """Replicate SAP's 'Auto Mesh at Joints': split every frame at any joint
    that lies on its span, so members that only touch mid-span (beams landing
    on an upright, brace crossings) actually connect.  Without this the raw
    SAP connectivity leaves those members dangling and the model is a
    mechanism.  Returns the number of members added."""
    import math
    nodes = model.nodes
    pts = [(nid, (n.x, n.y, n.z)) for nid, n in nodes.items()]
    next_id = max(model.members) + 1 if model.members else 1
    added = 0
    for mid in list(model.members):
        m = model.members[mid]
        a = nodes[m.node_i]
        b = nodes[m.node_j]
        ax, ay, az = a.x, a.y, a.z
        dx, dy, dz = b.x - ax, b.y - ay, b.z - az
        L2 = dx * dx + dy * dy + dz * dz
        if L2 < 1.0:
            continue
        interior = []
        for nid, (px, py, pz) in pts:
            if nid in (m.node_i, m.node_j):
                continue
            t = ((px - ax) * dx + (py - ay) * dy + (pz - az) * dz) / L2
            if t <= 1e-4 or t >= 1 - 1e-4:
                continue
            cx, cy, cz = ax + t * dx, ay + t * dy, az + t * dz
            if math.dist((px, py, pz), (cx, cy, cz)) <= tol:
                interior.append((t, nid))
        if not interior:
            continue
        interior.sort()
        chain = [m.node_i] + [nid for _, nid in interior] + [m.node_j]
        hi, hj = m.hinge_i, m.hinge_j
        origin = getattr(model, "frame_origin", {}).get(mid, mid)
        # first sub-member keeps the original id + its start hinge
        model.members[mid].node_j = chain[1]
        model.members[mid].hinge_j = hj if len(chain) == 2 else None
        for k in range(1, len(chain) - 1):
            new = next_id
            next_id += 1
            added += 1
            model.add_member(new, chain[k], chain[k + 1], m.section,
                             mtype=m.mtype,
                             hinge_j=hj if k == len(chain) - 2 else None,
                             mesh=m.mesh, member_set=m.member_set,
                             vecxz=m.vecxz)
            if hasattr(model, "frame_origin"):
                model.frame_origin[new] = origin
    return added


# ---------------------------------------------------------------- verify (1:1)
def verify_sap2000_import(model: RackModel, path: str) -> List[dict]:
    """Check the imported model against the SAP2000 workbook 1:1: node
    coordinates, member connectivity, section properties (A, I33, I22, J as
    SAP), supports and combination counts.  Rows {item, model, SAP, status}."""
    wb = _load(path)
    out: List[dict] = []

    def _fmt(v):
        if isinstance(v, (list, tuple, set)):
            return ", ".join(str(x) for x in sorted(v))
        return str(v)

    def add(item, mv, sv, ok):
        out.append({"item": item, "model": _fmt(mv), "SAP": _fmt(sv),
                    "status": "ok" if ok else "review"})

    def key(x, y, z):
        return (round(float(x)), round(float(y)), round(float(z)))

    # nodes
    _, joints = _table(wb, "Joint Coordinates")
    sap_nodes = {key(_f(r.get("GlobalX"), _f(r.get("XorR"))),
                     _f(r.get("GlobalY"), _f(r.get("Y"))),
                     _f(r.get("GlobalZ"), _f(r.get("Z")))) for r in joints}
    our_nodes = {key(n.x, n.y, n.z) for n in model.nodes.values()}
    add("nodes (by coordinate)", len(our_nodes), len(sap_nodes),
        our_nodes == sap_nodes)

    # frames vs members: the importer auto-meshes each SAP frame at joints on
    # its span (as SAP does), so a frame becomes a chain of members.  Verify
    # that every SAP frame's two endpoints are model nodes and lie on a member
    # chain, i.e. the geometry is reproduced (counts differ by the mesh).
    ncoord = {nid: key(n.x, n.y, n.z) for nid, n in model.nodes.items()}
    our_ends = set()
    for m in model.members.values():
        our_ends.add(ncoord[m.node_i])
        our_ends.add(ncoord[m.node_j])
    _, conn = _table(wb, "Connectivity - Frame")
    jc = {int(float(r["Joint"])): key(_f(r.get("GlobalX"), _f(r.get("XorR"))),
                                      _f(r.get("GlobalY"), _f(r.get("Y"))),
                                      _f(r.get("GlobalZ"), _f(r.get("Z"))))
          for r in joints}
    missing = 0
    for r in conn:
        i, j = int(float(r["JointI"])), int(float(r["JointJ"]))
        if jc.get(i) not in our_ends or jc.get(j) not in our_ends:
            missing += 1
    add("frames -> members (auto-meshed at joints)",
        f"{len(model.members)} members", f"{len(conn)} SAP frames",
        missing == 0)

    # section properties (A, I33->Iz, I22->Iy, J) for the used sections
    _, props = _table(wb, "Frame Props 01 - General")
    used = {m.section for m in model.members.values()}
    bad = 0
    checked = 0
    for r in props:
        name = r["SectionName"]
        if name not in used or name not in model.sections:
            continue
        checked += 1
        s = model.sections[name]
        for label, ours, theirs in (
                ("A", s.A, _f(r.get("Area"))),
                ("Iz=I33", s.Iz, _f(r.get("I33"))),
                ("Iy=I22", s.Iy, _f(r.get("I22"))),
                ("J", s.J, _f(r.get("TorsConst")))):
            if theirs and abs(ours - theirs) > max(1.0, 1e-4 * abs(theirs)):
                bad += 1
    add("section properties (A, I33, I22, J)", f"{checked} sections",
        f"{checked} sections", bad == 0)

    # supports
    _, restr = _table(wb, "Joint Restraint Assignments")
    add("supports (restrained joints)", len(model.supports), len(restr),
        len(model.supports) == len(restr))

    # load patterns and combinations
    _, pats = _table(wb, "Load Pattern Definitions")
    add("load patterns", len(model.load_cases), len(pats),
        len(model.load_cases) == len(pats))
    _, combos = _table(wb, "Combination Definitions")
    sap_combos = {r.get("ComboName") for r in combos if r.get("ComboName")}
    add("load combinations", len(model.combinations), len(sap_combos),
        len(model.combinations) == len(sap_combos))
    return out


# ---------------------------------------------------------------- export
_UNIT = {"len": "mm", "force": "N", "I": "mm4", "A": "mm2", "S": "mm3",
         "E": "N/mm2", "spr_t": "N/mm", "spr_r": "N-mm/rad",
         "w": "N/mm3", "line": "N/mm"}

# SAP identifies each imported table by the row-1 'TABLE:  <title>' text, NOT
# the (31-char-limited) sheet name.  Where the full SAP table name differs from
# the sheet name it must be written in full or SAP silently SKIPS the table
# (leaving e.g. no base springs / no member releases -> unstable structure).
_TABLE_TITLE = {
    "Jt Spring Assigns 1 - Uncoupled":
        "Joint Spring Assignments 1 - Uncoupled",
    "Frame Releases 1 - General": "Frame Release Assignments 1 - General",
    "Frame Releases 2 - Part Fixity":
        "Frame Release Assignments 2 - Partial Fixity",
    "Frame Local Axes 1 - Typical":
        "Frame Local Axes Assignments 1 - Typical",
    "Frame Props 01 - General": "Frame Section Properties 01 - General",
    "MatProp 01 - General": "Material Properties 01 - General",
    "MatProp 02 - Basic Mech Props":
        "Material Properties 02 - Basic Mechanical Properties",
    "MatProp 03a - Steel Data": "Material Properties 03a - Steel Data",
    "Case - Static 1 - Load Assigns":
        "Case - Static 1 - Load Assignments",
}

# Exact SAP2000 table schemas (header row + units row), taken verbatim from a
# real SAP2000 database Excel export.  The exporter writes every table on this
# schema and places each value by COLUMN NAME, so a value never lands in the
# wrong column regardless of whether SAP reads by name or position.
_SCHEMA = {
    "Program Control": (
        ["ProgramName", "Version", "ProgLevel", "LicenseNum", "LicenseOS",
         "LicenseSC", "LicenseHT", "CurrUnits", "SteelCode", "ConcCode",
         "AlumCode", "ColdCode", "ConcSCode", "RegenHinge"],
        ["Text", "Text", "Text", "Text", "Yes/No", "Yes/No", "Yes/No", "Text",
         "Text", "Text", "Text", "Text", "Text", "Yes/No"]),
    "Joint Coordinates": (
        ["Joint", "CoordSys", "CoordType", "XorR", "Y", "Z", "SpecialJt",
         "GlobalX", "GlobalY", "GlobalZ", "GUID"],
        ["Text", "Text", "Text", "mm", "mm", "mm", "Yes/No", "mm", "mm", "mm",
         "Text"]),
    "MatProp 01 - General": (
        ["Material", "Type", "Grade", "SymType", "TempDepend", "Color",
         "GUID", "Notes"],
        ["Text", "Text", "Text", "Text", "Yes/No", "Text", "Text", "Text"]),
    "MatProp 02 - Basic Mech Props": (
        ["Material", "UnitWeight", "UnitMass", "E1", "G12", "U12", "A1"],
        ["Text", "N/mm3", "N-s2/mm4", "N/mm2", "N/mm2", "Unitless", "1/C"]),
    "MatProp 03a - Steel Data": (
        ["Material", "Fy", "Fu", "EffFy", "EffFu", "SSCurveOpt", "SSHysType",
         "SHard", "SMax", "SRup", "FinalSlope", "CoupModType"],
        ["Text", "N/mm2", "N/mm2", "N/mm2", "N/mm2", "Text", "Text",
         "Unitless", "Unitless", "Unitless", "Unitless", "Text"]),
    "Frame Props 01 - General": (
        ["SectionName", "Material", "Shape", "t3", "t2", "tf", "tw",
         "FilletRadius", "Area", "TorsConst", "I33", "I22", "I23", "AS2",
         "AS3", "S33Top", "S33Bot", "S22Left", "S22Right", "Z33", "Z22",
         "R33", "R22", "CGOffset3", "CGOffset2", "EccV2", "EccV3", "Cw",
         "IncludeSCAn", "ConcCol", "ConcBeam", "Color", "TotalWt", "TotalMass",
         "FromFile", "AMod", "A2Mod", "A3Mod", "JMod", "I2Mod", "I3Mod",
         "MMod", "WMod", "GUID", "Notes"],
        ["Text", "Text", "Text", "mm", "mm", "mm", "mm", "mm", "mm2", "mm4",
         "mm4", "mm4", "mm4", "mm2", "mm2", "mm3", "mm3", "mm3", "mm3", "mm3",
         "mm3", "mm", "mm", "mm", "mm", "mm", "mm", "mm6", "Yes/No", "Yes/No",
         "Yes/No", "Text", "N", "N-s2/mm", "Yes/No", "Unitless", "Unitless",
         "Unitless", "Unitless", "Unitless", "Unitless", "Unitless",
         "Unitless", "Text", "Text"]),
    "Connectivity - Frame": (
        ["Frame", "JointI", "JointJ", "IsCurved", "Length", "CentroidX",
         "CentroidY", "CentroidZ", "GUID"],
        ["Text", "Text", "Text", "Yes/No", "mm", "mm", "mm", "mm", "Text"]),
    "Frame Section Assignments": (
        ["Frame", "SectionType", "AutoSelect", "AnalSect", "DesignSect",
         "MatProp"],
        ["Text", "Text", "Text", "Text", "Text", "Text"]),
    "Frame Property Modifiers": (
        ["Frame", "AMod", "AS2Mod", "AS3Mod", "JMod", "I22Mod", "I33Mod",
         "MassMod", "WeightMod", "EAModifier", "EIModifier"],
        ["Text"] + ["Unitless"] * 10),
    "Frame Releases 1 - General": (
        ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J", "V3J",
         "TJ", "M2J", "M3J", "PartialFix"],
        ["Text"] + ["Yes/No"] * 13),
    "Frame Releases 2 - Part Fixity": (
        ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J", "V3J",
         "TJ", "M2J", "M3J"],
        ["Text", "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad", "N-mm/rad",
         "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad", "N-mm/rad"]),
    "Frame Local Axes 1 - Typical": (
        ["Frame", "Angle", "AdvanceAxes"], ["Text", "Degrees", "Yes/No"]),
    "Joint Restraint Assignments": (
        ["Joint", "U1", "U2", "U3", "R1", "R2", "R3"],
        ["Text"] + ["Yes/No"] * 6),
    "Jt Spring Assigns 1 - Uncoupled": (
        ["Joint", "CoordSys", "U1", "U2", "U3", "R1", "R2", "R3"],
        ["Text", "Text", "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad",
         "N-mm/rad"]),
    "Load Pattern Definitions": (
        ["LoadPat", "DesignType", "SelfWtMult", "AutoLoad", "GUID", "Notes"],
        ["Text", "Text", "Unitless", "Text", "Text", "Text"]),
    "Load Case Definitions": (
        ["Case", "Type", "InitialCond", "ModalCase", "BaseCase", "MassSource",
         "DesTypeOpt", "DesignType", "DesActOpt", "DesignAct", "AutoType",
         "RunCase", "CaseStatus", "GUID", "Notes"],
        ["Text", "Text", "Text", "Text", "Text", "Text", "Text", "Text",
         "Text", "Text", "Text", "Yes/No", "Text", "Text", "Text"]),
    "Case - Static 1 - Load Assigns": (
        ["Case", "LoadType", "LoadName", "LoadSF"],
        ["Text", "Text", "Text", "Unitless"]),
    "Joint Loads - Force": (
        ["Joint", "LoadPat", "CoordSys", "F1", "F2", "F3", "M1", "M2", "M3",
         "GUID"],
        ["Text", "Text", "Text", "N", "N", "N", "N-mm", "N-mm", "N-mm",
         "Text"]),
    "Frame Loads - Distributed": (
        ["Frame", "LoadPat", "CoordSys", "Type", "Dir", "DistType", "RelDistA",
         "RelDistB", "AbsDistA", "AbsDistB", "FOverLA", "FOverLB", "GUID"],
        ["Text", "Text", "Text", "Text", "Text", "Text", "Unitless",
         "Unitless", "mm", "mm", "N/mm", "N/mm", "Text"]),
    "Combination Definitions": (
        ["ComboName", "ComboType", "AutoDesign", "CaseType", "CaseName",
         "ScaleFactor", "SteelDesign", "ConcDesign", "AlumDesign",
         "ColdDesign", "GUID", "Notes"],
        ["Text", "Text", "Yes/No", "Text", "Text", "Unitless", "Text", "Text",
         "Text", "Text", "Text", "Text"]),
}


def _is_axis_swapped(model: RackModel, m) -> bool:
    """True when the member's vecxz swaps the two transverse axes relative to
    this app's default (a rack-upright 90 deg rotation), so the SAP export must
    carry a 90 deg local-axis angle to reproduce the orientation on re-import."""
    v = getattr(m, "vecxz", None)
    if v is None:
        return False
    import math
    a = model.nodes[m.node_i]
    b = model.nodes[m.node_j]
    dz = abs(b.z - a.z)
    L = math.dist((a.x, a.y, a.z), (b.x, b.y, b.z)) or 1.0
    if dz / L > 0.999:                          # vertical: default vecxz=(0,1,0)
        return abs(v[0]) > abs(v[1])            # swapped -> ~(1,0,0)
    return abs(v[2]) > 0.5                       # non-vertical swap -> z-ish


def to_sap2000(model: RackModel, path: str,
               with_imperfections: bool = True) -> str:
    """Write the model as a SAP2000 database-tables workbook (N, mm) that
    re-imports into SAP2000 (File -> Import -> SAP2000 MS Excel Spreadsheet
    .xlsx).  Node coordinates, frame connectivity + section assignments,
    section properties (our Iz -> SAP I33, Iy -> I22), materials, member end
    releases + partial-fixity springs, restraints, load patterns, joint /
    frame loads and combinations.  Stiffness modifiers are written as 1.0 (any
    SAP EI/EA reduction is already reflected in the material E)."""
    import openpyxl
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def emit(name, row_dicts):
        # every table uses SAP's exact schema; values are placed by column
        # name, blanks for anything the app does not carry.  Sheet name is
        # <=31 chars; row-1 TABLE title is the full SAP name.
        header, units = _SCHEMA[name]
        ws = wb.create_sheet(name[:31])
        full = _TABLE_TITLE.get(name, name)
        ws.append([f"TABLE:  {full}"] + [None] * (len(header) - 1))
        ws.append(list(header))
        ws.append(list(units))
        for d in row_dicts:
            ws.append([d.get(h, "") for h in header])

    emit("Program Control", [{
        "ProgramName": "SAP2000", "Version": "26.0.0", "ProgLevel": "Ultimate",
        "LicenseOS": "Yes", "LicenseSC": "Yes", "LicenseHT": "No",
        "CurrUnits": "N, mm, C", "SteelCode": "AISC 360-10",
        "ConcCode": "ACI 318-14", "AlumCode": "AA 2015",
        "ColdCode": "AISI-ASD96", "ConcSCode": "Eurocode 2-2004",
        "RegenHinge": "Yes"}])

    # joints
    emit("Joint Coordinates", [{
        "Joint": str(nid), "CoordSys": "GLOBAL", "CoordType": "Cartesian",
        "XorR": n.x, "Y": n.y, "Z": n.z, "SpecialJt": "No",
        "GlobalX": n.x, "GlobalY": n.y, "GlobalZ": n.z}
        for nid, n in sorted(model.nodes.items())])

    # materials
    emit("MatProp 01 - General", [{
        "Material": mat.name, "Type": "Steel", "Grade": mat.name,
        "SymType": "Isotropic", "TempDepend": "No", "Color": "Yellow"}
        for mat in model.materials.values()])
    emit("MatProp 02 - Basic Mech Props", [{
        "Material": mat.name, "UnitWeight": 7.698e-5, "UnitMass": 7.849e-9,
        "E1": mat.E, "G12": mat.G, "U12": mat.nu, "A1": 1.17e-5}
        for mat in model.materials.values()])
    # steel data: the stress-strain-curve fields are only used by nonlinear
    # hinge/fiber material models; fill them with SAP's own conventions
    # (Eff = 1.1x, IS-steel curve constants, Von Mises) so the import is
    # warning-free instead of "blank; default value is used" x7 per material
    emit("MatProp 03a - Steel Data", [{
        "Material": mat.name, "Fy": mat.fy,
        "Fu": (fu := max(mat.fy * 1.5, mat.fy + 100.0)),
        "EffFy": 1.1 * mat.fy, "EffFu": 1.1 * fu,
        "SSCurveOpt": "Simple", "SSHysType": "Kinematic",
        "SHard": 0.01875, "SMax": 0.125, "SRup": 0.23,
        "FinalSlope": -0.1, "CoupModType": "Von Mises"}
        for mat in model.materials.values()])

    # section properties (Iz -> I33, Iy -> I22).  'General' shape -> SAP uses
    # these exact A / I33 / I22 / J instead of recomputing from a nominal
    # shape (CSI KB: "for general sections, resultant section properties are
    # directly entered" in Frame Section Properties 01 - General).  SAP's
    # General definition carries the COMPLETE property set, so every field it
    # fills in its own export is filled here: plastic moduli (Z), radii of
    # gyration (R = sqrt(I/A)), warping constant Cw, display colour and the
    # per-section totals of weight and mass over the members using it.
    def _shear(s, *names):
        for a in names:
            v = getattr(s, a, None)
            if v:
                return v
        return None
    length_of = {}                             # section -> total member length
    for m in model.members.values():
        length_of[m.section] = (length_of.get(m.section, 0.0)
                                + model.member_length(m))
    _COLORS = ["Green", "Red", "Yellow", "Cyan", "Magenta", "Blue"]
    GAMMA = 7.698e-5                           # steel unit weight [N/mm3]
    pr = []
    for i, s in enumerate(model.sections.values()):
        t3 = s.depth_h or (2.0 * s.Iz / s.Welz if s.Welz else 100.0)
        t2 = s.width_b or (2.0 * s.Iy / s.Wely if s.Wely else 50.0)
        wt = s.A * GAMMA * length_of.get(s.name, 0.0)
        pr.append({
            "SectionName": s.name, "Material": s.material, "Shape": "General",
            "t3": t3, "t2": t2, "tf": 0, "tw": 0, "FilletRadius": 0,
            "Area": s.A, "TorsConst": s.J, "I33": s.Iz, "I22": s.Iy, "I23": 0,
            "AS2": _shear(s, "Az", "shear_z", "Avz") or s.A,
            "AS3": _shear(s, "Ay", "shear_y", "Avy") or s.A,
            "S33Top": s.Welz, "S33Bot": s.Welz, "S22Left": s.Wely,
            "S22Right": s.Wely,
            # plastic moduli: tested/effective plastic values are not part of
            # the EN 15512 data set; Z=Wel (elastic) is entered - analysis
            # ignores Z and any SAP steel design would then be elastic-safe
            "Z33": getattr(s, "Wplz", None) or s.Welz,
            "Z22": getattr(s, "Wply", None) or s.Wely,
            "R33": (s.Iz / s.A) ** 0.5, "R22": (s.Iy / s.A) ** 0.5,
            "CGOffset3": 0, "CGOffset2": 0, "EccV2": 0, "EccV3": 0,
            "Cw": getattr(s, "Iw_gross", None) or 0,
            "IncludeSCAn": "No", "ConcCol": "No", "ConcBeam": "No",
            "Color": _COLORS[i % len(_COLORS)],
            "TotalWt": wt, "TotalMass": wt / 9810.0, "FromFile": "No",
            "AMod": 1, "A2Mod": 1, "A3Mod": 1, "JMod": 1, "I2Mod": 1,
            "I3Mod": 1, "MMod": 1, "WMod": 1})
    emit("Frame Props 01 - General", pr)

    # frames + assignments + local-axis rotation
    cf, fa, fmod, la = [], [], [], []
    for mid, m in sorted(model.members.items()):
        _a, _b = model.nodes[m.node_i], model.nodes[m.node_j]
        cf.append({"Frame": str(mid), "JointI": str(m.node_i),
                   "JointJ": str(m.node_j), "IsCurved": "No",
                   "Length": round(model.member_length(m), 3),
                   "CentroidX": round((_a.x + _b.x) / 2, 3),
                   "CentroidY": round((_a.y + _b.y) / 2, 3),
                   "CentroidZ": round((_a.z + _b.z) / 2, 3)})
        fa.append({"Frame": str(mid), "SectionType": "General",
                   "AutoSelect": "N.A.", "AnalSect": m.section,
                   "DesignSect": m.section, "MatProp": "Default"})
        fmod.append({"Frame": str(mid), "AMod": 1, "AS2Mod": 1, "AS3Mod": 1,
                     "JMod": 1, "I22Mod": 1, "I33Mod": 1, "MassMod": 1,
                     "WeightMod": 1, "EAModifier": 1, "EIModifier": 1})
        if _is_axis_swapped(model, m):
            la.append({"Frame": str(mid), "Angle": 90, "AdvanceAxes": "No"})
    emit("Connectivity - Frame", cf)
    emit("Frame Section Assignments", fa)
    emit("Frame Property Modifiers", fmod)
    if la:
        emit("Frame Local Axes 1 - Typical", la)

    # releases (rz -> M3, ry -> M2, rx -> T); spring -> partial fixity
    rel1, rel2 = [], []

    def _flag(v):
        return "Yes" if v is not None else "No"
    for mid, m in sorted(model.members.items()):
        hi, hj = m.hinge_i, m.hinge_j
        if not hi and not hj and m.mtype != "truss":
            continue
        if m.mtype == "truss":                 # pin both ends (axial only)
            rel1.append({"Frame": str(mid), "PI": "No", "V2I": "No",
                         "V3I": "No", "TI": "No", "M2I": "Yes", "M3I": "Yes",
                         "PJ": "No", "V2J": "No", "V3J": "No", "TJ": "No",
                         "M2J": "Yes", "M3J": "Yes", "PartialFix": "No"})
            continue
        pf = any(isinstance(getattr(h, a, None), float) and getattr(h, a) > 0
                 for h in (hi, hj) for a in ("rx", "ry", "rz"))
        rel1.append({
            "Frame": str(mid), "PI": "No", "V2I": "No", "V3I": "No",
            "TI": _flag(getattr(hi, "rx", None)),
            "M2I": _flag(getattr(hi, "ry", None)),
            "M3I": _flag(getattr(hi, "rz", None)),
            "PJ": "No", "V2J": "No", "V3J": "No",
            "TJ": _flag(getattr(hj, "rx", None)),
            "M2J": _flag(getattr(hj, "ry", None)),
            "M3J": _flag(getattr(hj, "rz", None)),
            "PartialFix": "Yes" if pf else "No"})
        if pf:
            def _spr(h, a):
                v = getattr(h, a, None) if h else None
                return v if isinstance(v, float) and v > 0 else ""
            rel2.append({
                "Frame": str(mid), "TI": _spr(hi, "rx"), "M2I": _spr(hi, "ry"),
                "M3I": _spr(hi, "rz"), "TJ": _spr(hj, "rx"),
                "M2J": _spr(hj, "ry"), "M3J": _spr(hj, "rz")})
    emit("Frame Releases 1 - General", rel1)
    emit("Frame Releases 2 - Part Fixity", rel2)

    # restraints (fixed DOFs) + Jt Spring Assigns (semi-rigid base springs)
    def _yn(d):
        return "Yes" if d is True else "No"
    rr, jspr = [], []
    for s in model.supports:
        rr.append({"Joint": str(s.node), "U1": _yn(s.ux), "U2": _yn(s.uy),
                   "U3": _yn(s.uz), "R1": _yn(s.rx), "R2": _yn(s.ry),
                   "R3": _yn(s.rz)})

        def sv(d):
            return d if isinstance(d, float) and d > 0 else 0
        if any(isinstance(getattr(s, a), float)
               for a in ("ux", "uy", "uz", "rx", "ry", "rz")):
            jspr.append({"Joint": str(s.node), "CoordSys": "Local",
                         "U1": sv(s.ux), "U2": sv(s.uy), "U3": sv(s.uz),
                         "R1": sv(s.rx), "R2": sv(s.ry), "R3": sv(s.rz)})
    emit("Joint Restraint Assignments", rr)
    if jspr:
        emit("Jt Spring Assigns 1 - Uncoupled", jspr)

    # ---- sway imperfection as EHF notional load patterns -------------------
    # this app applies the EN 15512 sway as equivalent horizontal forces
    # phi * V at every downward load; SAP models it the same way (explicit
    # notional joint loads).  Expand each imperfection-carrying combination
    # per direction (as this app runs it) into a dedicated IMP pattern.
    from .combos import assemble
    from .model import DIRECTION_VECTORS
    imp = model.imperfection
    phi = 0.0
    if with_imperfections and hasattr(imp, "value"):
        try:
            phi = imp.value()
        except Exception:
            phi = 0.0
    imp_patterns: Dict[str, List[dict]] = {}   # pattern name -> joint-load rows
    expanded: List[Tuple[str, Dict[str, float], Optional[str]]] = []
    for c in model.combinations:
        dirs = [None]
        if with_imperfections and phi and getattr(c, "imperfection", False):
            dirs = (getattr(c, "imp_directions", None)
                    or getattr(imp, "directions", ["+x"]))
        for d in dirs:
            pat = None
            if d:
                pat = f"IMP_{c.name}_{d}".replace("@", "_").replace(" ", "_")
                dx, dy = DIRECTION_VECTORS[d]
                loads = assemble(model, c)
                acc: Dict[int, float] = {}
                for node, f in loads.nodal.items():
                    if f[2] < 0.0:
                        acc[node] = acc.get(node, 0.0) + phi * abs(f[2])
                for mid, q in loads.member.items():
                    if q[2] < 0.0:
                        mm = model.members[mid]
                        h = phi * abs(q[2]) * model.member_length(mm) / 2.0
                        acc[mm.node_i] = acc.get(mm.node_i, 0.0) + h
                        acc[mm.node_j] = acc.get(mm.node_j, 0.0) + h
                imp_patterns[pat] = [
                    {"Joint": str(n), "LoadPat": pat, "CoordSys": "GLOBAL",
                     "F1": round(dx * v, 4), "F2": round(dy * v, 4),
                     "F3": 0, "M1": 0, "M2": 0, "M3": 0}
                    for n, v in acc.items() if abs(v) > 1e-9]
            expanded.append((c.name if not d else f"{c.name}_{d}".replace(
                "@", "_"), dict(c.factors), pat))

    # load patterns / cases (gravity + the imperfection patterns)
    names = list(model.load_cases) + list(imp_patterns)
    emit("Load Pattern Definitions", [{
        "LoadPat": name,
        "DesignType": "Other" if name in imp_patterns else (
            "Dead" if str(name).lower().startswith("dead") else "Live"),
        "SelfWtMult": 0, "AutoLoad": ""} for name in names])
    emit("Load Case Definitions", [{
        "Case": name, "Type": "LinStatic", "InitialCond": "Zero",
        "DesTypeOpt": "Prog Det",
        "DesignType": "Dead" if str(name).lower().startswith("dead")
        else "Live", "DesActOpt": "Prog Det", "DesignAct": "Non-Composite",
        "AutoType": "None", "RunCase": "Yes", "CaseStatus": "Not Run"}
        for name in names])
    # a LinStatic case only carries load once it is told which pattern to apply
    # (without this table the cases run with zero load -> "loads not assigned")
    emit("Case - Static 1 - Load Assigns", [{
        "Case": name, "LoadType": "Load pattern", "LoadName": name,
        "LoadSF": 1} for name in names])

    # loads (gravity load cases + the imperfection joint loads)
    jf, fd = [], []
    for name, lc in model.load_cases.items():
        for nl in lc.nodal_loads:
            jf.append({"Joint": str(nl.node), "LoadPat": name,
                       "CoordSys": "GLOBAL", "F1": nl.fx, "F2": nl.fy,
                       "F3": nl.fz, "M1": nl.mx, "M2": nl.my, "M3": nl.mz})
        for ml in lc.member_loads:
            if abs(ml.qz) < 1e-12:
                continue
            L = model.member_length(model.members[ml.member])
            fd.append({"Frame": str(ml.member), "LoadPat": name,
                       "CoordSys": "GLOBAL", "Type": "Force", "Dir": "Gravity",
                       "DistType": "RelDist", "RelDistA": 0, "RelDistB": 1,
                       "AbsDistA": 0, "AbsDistB": round(L, 3),
                       "FOverLA": abs(ml.qz), "FOverLB": abs(ml.qz)})
    for rows_ in imp_patterns.values():
        jf.extend(rows_)
    emit("Joint Loads - Force", jf)
    emit("Frame Loads - Distributed", fd)

    # combinations (expanded per imperfection direction, each adding its IMP
    # pattern at factor 1 - the EHF magnitude already carries the phi*gravity)
    cd = []
    for cname, factors, pat in expanded:
        first = True
        for case, sf in factors.items():
            row = {"ComboName": cname,
                   "ComboType": "Linear Add" if first else "",
                   "AutoDesign": "No", "CaseType": "Linear Static",
                   "CaseName": case, "ScaleFactor": sf}
            if first:
                row.update({"SteelDesign": "None", "ConcDesign": "None",
                            "AlumDesign": "None", "ColdDesign": "None"})
            cd.append(row)
            first = False
        if pat:
            cd.append({"ComboName": cname, "AutoDesign": "No",
                       "CaseType": "Linear Static", "CaseName": pat,
                       "ScaleFactor": 1.0})
    emit("Combination Definitions", cd)

    wb.save(path)
    return path


# ---------------------------------------------------------------- results
def read_sap_element_forces(path) -> Dict[str, Dict[int, dict]]:
    """SAP2000 'Element Forces - Frames' results -> per OutputCase, per SAP
    FRAME: the envelope over all stations {N_min, N_max, My_absmax,
    Mz_absmax} in base units [N, N*mm], mapped to this app's axes (SAP M3 major
    -> our Mz, M2 minor -> our My).  MODAL / mode-shape cases are skipped."""
    wbs = _load(path)
    rows = _sheet_rows(wbs, "Element Forces - Frames")
    if not rows:
        return {}
    hdr = [("" if c is None else str(c).strip()) for c in rows[1]]
    ix = {h: i for i, h in enumerate(hdr)}
    fN, fV, fM2, fM3 = ix.get("P"), ix.get("V2"), ix.get("M2"), ix.get("M3")
    fc, ff = ix.get("OutputCase"), ix.get("Frame")
    out: Dict[str, Dict[int, dict]] = {}
    for r in rows[3:]:
        if r is None or r[ff] in (None, "") or r[fc] in (None, ""):
            continue
        case = str(r[fc])
        if case.upper() == "MODAL":
            continue
        try:
            frame = int(float(r[ff]))
            N = float(r[fN])
            my = float(r[fM2])              # SAP M2 -> our My
            mz = float(r[fM3])              # SAP M3 -> our Mz
        except (TypeError, ValueError):
            continue
        d = out.setdefault(case, {}).setdefault(
            frame, {"N_min": 0.0, "N_max": 0.0, "My": 0.0, "Mz": 0.0})
        d["N_min"] = min(d["N_min"], N)
        d["N_max"] = max(d["N_max"], N)
        d["My"] = max(d["My"], abs(my))
        d["Mz"] = max(d["Mz"], abs(mz))
    return out


def read_sap_base_reactions(path) -> Dict[str, dict]:
    """SAP2000 'Base Reactions' -> {OutputCase: {FX, FY, FZ} [N]} (first/only
    step per case; modal steps collapsed to the case name)."""
    wbs = _load(path)
    _, rows = _table(wbs, "Base Reactions")
    out: Dict[str, dict] = {}
    for r in rows:
        case = r.get("OutputCase")
        if not case or str(case).upper() == "MODAL" or case in out:
            continue
        out[case] = {"FX": _f(r.get("GlobalFX"), 0.0),
                     "FY": _f(r.get("GlobalFY"), 0.0),
                     "FZ": _f(r.get("GlobalFZ"), 0.0)}
    return out


def compare_sap_forces(model: RackModel, cases, sap: Dict[str, Dict[int, dict]],
                       case_map: Optional[Dict[str, str]] = None) -> List[dict]:
    """Compare this app's member forces with SAP's 'Element Forces - Frames'
    per SAP FRAME (the app auto-meshes each frame into sub-members, so both
    sides are enveloped back to the original frame).  case_map maps an app
    combo/case name to the SAP OutputCase name (default: identical names).
    Returns one row per (case, frame) with N / My / Mz, app vs SAP, and the
    per-component difference + tolerance status."""
    from .rfem_compare import _pct, within_tolerance
    origin = getattr(model, "frame_origin", {mid: mid for mid in model.members})
    case_map = case_map or {}
    KN, KNCM = 1.0e3, 1.0e4
    rows: List[dict] = []
    for case in cases:
        if not getattr(case, "converged", False):
            continue
        sap_case = case_map.get(case.combo, case.combo)
        ref = sap.get(sap_case)
        if ref is None:
            continue
        # envelope our sub-member station forces back to the SAP frame
        frame_env: Dict[int, dict] = {}
        for mid, mr in case.members.items():
            fr = origin.get(mid, mid)
            e = frame_env.setdefault(fr, {"N": 0.0, "My": 0.0, "Mz": 0.0,
                                          "sec": model.members[mid].section})
            e["N"] = min(e["N"], mr.N_min)
            e["My"] = max(e["My"], mr.My_absmax)
            e["Mz"] = max(e["Mz"], mr.Mz_absmax)
        for fr, e in frame_env.items():
            s = ref.get(fr)
            if s is None:
                continue
            trip = [("N", e["N"], s["N_min"], KN, "kN"),
                    ("My", e["My"], s["My"], KNCM, "kNcm"),
                    ("Mz", e["Mz"], s["Mz"], KNCM, "kNcm")]
            row = {"case": sap_case, "frame": fr, "section": e["sec"]}
            worst, ok = 0.0, True
            qmap = {"N": "N_min", "My": "My_absmax", "Mz": "Mz_absmax"}
            for tag, ours, theirs, div, unit in trip:
                row[f"{tag} ours [{unit}]"] = round(ours / div, 3)
                row[f"{tag} SAP [{unit}]"] = round(theirs / div, 3)
                d = _pct(ours, theirs)
                row[f"{tag} Δ%"] = d
                worst = max(worst, d)
                if not within_tolerance(qmap[tag], ours, theirs):
                    ok = False
            row["max Δ%"] = worst
            row["status"] = "ok" if ok else "review"
            rows.append(row)
    rows.sort(key=lambda r: -r["max Δ%"])
    return rows


def read_sap_joint_displacements(path) -> Dict[str, Dict[int, tuple]]:
    """SAP2000 'Joint Displacements' -> {OutputCase: {joint: (U1, U2, U3)}} in
    mm (global X, Y, Z).  MODAL / mode-shape cases are skipped."""
    wbs = _load(path)
    rows = _sheet_rows(wbs, "Joint Displacements")
    if not rows:
        return {}
    hdr = [("" if c is None else str(c).strip()) for c in rows[1]]
    ix = {h: i for i, h in enumerate(hdr)}
    ji, ci = ix.get("Joint"), ix.get("OutputCase")
    u1, u2, u3 = ix.get("U1"), ix.get("U2"), ix.get("U3")
    out: Dict[str, Dict[int, tuple]] = {}
    for r in rows[3:]:
        if r is None or r[ji] in (None, "") or r[ci] in (None, ""):
            continue
        case = str(r[ci])
        if case.upper() == "MODAL":
            continue
        try:
            j = int(float(r[ji]))
            d = (float(r[u1]), float(r[u2]), float(r[u3]))
        except (TypeError, ValueError):
            continue
        out.setdefault(case, {})[j] = d
    return out


def compare_sap_displacements(model: RackModel, cases,
                              sap: Dict[str, Dict[int, tuple]],
                              case_map: Optional[Dict[str, str]] = None,
                              floor: float = 0.1) -> List[dict]:
    """Compare this app's joint displacements with SAP's 'Joint Displacements'
    per node (global U1/U2/U3 [mm]).  case_map maps an app combo to the SAP
    OutputCase (default identical).  Only nodes whose displacement magnitude
    exceeds `floor` mm on either side are reported (sub-floor noise dropped).
    One row per (case, node)."""
    from .rfem_compare import _pct, within_tolerance
    case_map = case_map or {}
    rows: List[dict] = []
    for case in cases:
        if not getattr(case, "converged", False):
            continue
        sc = case_map.get(case.combo, case.combo)
        ref = sap.get(sc)
        if not ref:
            continue
        for nid, d in case.displacements.items():
            s = ref.get(nid)
            if s is None:
                continue
            ours = (d[0], d[1], d[2])
            if max(max(abs(v) for v in ours),
                   max(abs(v) for v in s)) < floor:
                continue
            row = {"case": sc, "node": nid}
            worst, ok = 0.0, True
            for tag, o, t in (("U1(X)", ours[0], s[0]),
                              ("U2(Y)", ours[1], s[1]),
                              ("U3(Z)", ours[2], s[2])):
                row[f"{tag} ours [mm]"] = round(o, 3)
                row[f"{tag} SAP [mm]"] = round(t, 3)
                dd = _pct(o, t)
                row[f"{tag} Δ%"] = dd
                worst = max(worst, dd)
                # absolute floor of 0.5 mm for the tolerance verdict
                if abs(o - t) > 0.5 and dd > 15.0:
                    ok = False
            row["max Δ%"] = worst
            row["status"] = "ok" if ok else "review"
            rows.append(row)
    rows.sort(key=lambda r: -r["max Δ%"])
    return rows
