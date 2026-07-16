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
    import openpyxl
    return openpyxl.load_workbook(path, data_only=True, read_only=True)


def _table(wb, name: str) -> Tuple[List[str], List[dict]]:
    """Return (header, [row-dict]) for a SAP table sheet.  Row 1 is the
    'TABLE: ...' title, row 2 the column names, row 3 the units, data from
    row 4."""
    for sheet in wb.sheetnames:
        if sheet.strip() == name or sheet.strip().startswith(name):
            rows = list(wb[sheet].iter_rows(values_only=True))
            if len(rows) < 2:
                return [], []
            hdr = [("" if c is None else str(c).strip()) for c in rows[1]]
            out = []
            for r in rows[3:]:
                if r is None or r[0] in (None, ""):
                    continue
                out.append({hdr[i]: r[i] for i in range(min(len(hdr), len(r)))})
            return hdr, out
    return [], []


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
    sec_of = {str(r["Frame"]): (r.get("AnalSect") or r.get("DesignSect"))
              for r in assign}
    for r in conn:
        fid = int(float(r["Frame"]))
        sec = sec_of.get(str(r["Frame"]))
        if sec not in model.sections:
            continue
        role = model.sections[sec].role
        mtype = "truss" if role == "bracing" else "beam"
        hi, hj = releases.get(str(r["Frame"]), (None, None))
        model.add_member(fid, int(float(r["JointI"])), int(float(r["JointJ"])),
                         sec, mtype=mtype,
                         hinge_i=hi if mtype == "beam" else None,
                         hinge_j=hj if mtype == "beam" else None,
                         mesh=2 if mtype == "beam" else 1,
                         member_set=role or sec)

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

    # ---- load patterns / cases --------------------------------------------
    _, pats = _table(wb, "Load Pattern Definitions")
    selfwt = {r["LoadPat"]: _f(r.get("SelfWtMult"), 0.0) for r in pats}
    cases: Dict[str, LoadCase] = {}
    for name in selfwt:
        kind = "permanent" if str(name).upper().startswith("DEAD") \
            else "variable"
        cases[name] = LoadCase(name, kind)

    # self-weight member UDLs
    for name, mult in selfwt.items():
        if not mult:
            continue
        for m in model.members.values():
            sec = model.sections[m.section]
            g = gamma.get(sec.material, 7.7e-5)
            w = sec.A * g * mult                 # N/mm
            cases[name].member_loads.append(MemberLoad(m.id, qz=-w))

    # distributed frame loads (gravity)
    _, dist = _table(wb, "Frame Loads - Distributed")
    for r in dist:
        pat = r.get("LoadPat")
        if pat not in cases:
            cases[pat] = LoadCase(pat, "variable")
        fid = int(float(r["Frame"]))
        if fid not in model.members:
            continue
        w = _f(r.get("FOverLA"), 0.0)
        d = str(r.get("Dir", "Gravity")).lower()
        ml = MemberLoad(fid)
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
        model.combinations.append(Combination(
            name, kind, fac, imperfection=False,
            order=2 if kind == "ULS" else 1))

    _automesh_at_joints(model)
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


def to_sap2000(model: RackModel, path: str) -> str:
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

    def sheet(title, header, units, rows):
        ws = wb.create_sheet(title[:31])
        ws.append([f"TABLE:  {title}"] + [None] * (len(header) - 1))
        ws.append(header)
        ws.append(units)
        for r in rows:
            ws.append(r)

    sheet("Program Control",
          ["ProgramName", "Version", "CurrUnits", "SteelCode"],
          ["Text", "Text", "Text", "Text"],
          [["SAP2000", "26.0.0", "N, mm, C", "AISC 360-10"]])

    # joints
    jr = [[str(nid), "GLOBAL", "Cartesian", n.x, n.y, n.z, "No",
           n.x, n.y, n.z] for nid, n in sorted(model.nodes.items())]
    sheet("Joint Coordinates",
          ["Joint", "CoordSys", "CoordType", "XorR", "Y", "Z", "SpecialJt",
           "GlobalX", "GlobalY", "GlobalZ"],
          ["Text", "Text", "Text", "mm", "mm", "mm", "Yes/No", "mm", "mm",
           "mm"], jr)

    # materials
    mg, mm2, m3a = [], [], []
    for mat in model.materials.values():
        mg.append([mat.name, "Steel", mat.name, "Isotropic", "No"])
        mm2.append([mat.name, 7.698e-5, 7.849e-9, mat.E, mat.G, mat.nu,
                    1.17e-5])
        m3a.append([mat.name, mat.fy, max(mat.fy * 1.5, mat.fy + 100.0)])
    sheet("MatProp 01 - General",
          ["Material", "Type", "Grade", "SymType", "TempDepend"],
          ["Text", "Text", "Text", "Text", "Yes/No"], mg)
    sheet("MatProp 02 - Basic Mech Props",
          ["Material", "UnitWeight", "UnitMass", "E1", "G12", "U12", "A1"],
          ["Text", "N/mm3", "N-s2/mm4", "N/mm2", "N/mm2", "Unitless", "1/C"],
          mm2)
    sheet("MatProp 03a - Steel Data", ["Material", "Fy", "Fu"],
          ["Text", "N/mm2", "N/mm2"], m3a)

    # section properties (Iz -> I33, Iy -> I22)
    pr = []
    for s in model.sections.values():
        pr.append([s.name, s.material, "Box/Tube", s.depth_h or 0,
                   s.width_b or 0, s.A, s.J, s.Iz, s.Iy, s.Welz, s.Wely])
    sheet("Frame Props 01 - General",
          ["SectionName", "Material", "Shape", "t3", "t2", "Area",
           "TorsConst", "I33", "I22", "S33", "S22"],
          ["Text", "Text", "Text", "mm", "mm", "mm2", "mm4", "mm4", "mm4",
           "mm3", "mm3"], pr)

    # frames + assignments
    cf, fa, fmod, la = [], [], [], []
    for mid, m in sorted(model.members.items()):
        cf.append([str(mid), str(m.node_i), str(m.node_j), "No",
                   round(model.member_length(m), 3)])
        stype = "Section Designer" if model.sections[m.section].role \
            == "uprights" else "Frame"
        fa.append([str(mid), stype, "N.A.", m.section, m.section, "Default"])
        fmod.append([str(mid), 1, 1, 1, 1, 1, 1, 1, 1, 1, 1])
    sheet("Connectivity - Frame",
          ["Frame", "JointI", "JointJ", "IsCurved", "Length"],
          ["Text", "Text", "Text", "Yes/No", "mm"], cf)
    sheet("Frame Section Assignments",
          ["Frame", "SectionType", "AutoSelect", "AnalSect", "DesignSect",
           "MatProp"], ["Text", "Text", "Text", "Text", "Text", "Text"], fa)
    sheet("Frame Property Modifiers",
          ["Frame", "AMod", "AS2Mod", "AS3Mod", "JMod", "I22Mod", "I33Mod",
           "MassMod", "WeightMod", "EAModifier", "EIModifier"],
          ["Text"] + ["Unitless"] * 10, fmod)

    # releases (rz -> M3, ry -> M2, rx -> T); spring -> partial fixity
    rel1, rel2 = [], []

    def _flag(v):
        return "Yes" if v is not None else "No"
    for mid, m in sorted(model.members.items()):
        hi, hj = m.hinge_i, m.hinge_j
        if not hi and not hj and m.mtype != "truss":
            continue
        if m.mtype == "truss":                 # pin both ends (axial only)
            rel1.append([str(mid), "No", "No", "No", "No", "Yes", "Yes",
                         "No", "No", "No", "No", "Yes", "Yes", "No"])
            continue
        row = [str(mid),
               "No", "No", "No", _flag(getattr(hi, "rx", None)),
               _flag(getattr(hi, "ry", None)), _flag(getattr(hi, "rz", None)),
               "No", "No", "No", _flag(getattr(hj, "rx", None)),
               _flag(getattr(hj, "ry", None)), _flag(getattr(hj, "rz", None))]
        pf = any(isinstance(getattr(h, a, None), float)
                 and getattr(h, a) > 0
                 for h in (hi, hj) for a in ("rx", "ry", "rz"))
        row.append("Yes" if pf else "No")
        rel1.append(row)
        if pf:
            def _spr(h, a):
                v = getattr(h, a, None) if h else None
                return v if isinstance(v, float) and v > 0 else None
            rel2.append([str(mid), None, None, None, _spr(hi, "rx"),
                         _spr(hi, "ry"), _spr(hi, "rz"), None, None, None,
                         _spr(hj, "rx"), _spr(hj, "ry"), _spr(hj, "rz")])
    sheet("Frame Releases 1 - General",
          ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J",
           "V3J", "TJ", "M2J", "M3J", "PartialFix"],
          ["Text"] + ["Yes/No"] * 13, rel1)
    sheet("Frame Releases 2 - Part Fixity",
          ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J",
           "V3J", "TJ", "M2J", "M3J"],
          ["Text", "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad",
           "N-mm/rad", "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad",
           "N-mm/rad"], rel2)

    # restraints
    def _yn(d):
        return "Yes" if d is True else "No"
    rr = [[str(s.node), _yn(s.ux), _yn(s.uy), _yn(s.uz),
           _yn(s.rx), _yn(s.ry), _yn(s.rz)] for s in model.supports]
    sheet("Joint Restraint Assignments",
          ["Joint", "U1", "U2", "U3", "R1", "R2", "R3"],
          ["Text"] + ["Yes/No"] * 6, rr)

    # load patterns / cases
    lp, lcd = [], []
    for name, lc in model.load_cases.items():
        swm = 1 if str(name).upper().startswith("DEAD") else 0
        dtype = "Dead" if swm else "Live"
        lp.append([name, dtype, swm, ""])
        lcd.append([name, "LinStatic", "Zero", "Yes"])
    sheet("Load Pattern Definitions",
          ["LoadPat", "DesignType", "SelfWtMult", "AutoLoad"],
          ["Text", "Text", "Unitless", "Text"], lp)
    sheet("Load Case Definitions",
          ["Case", "Type", "InitialCond", "RunCase"],
          ["Text", "Text", "Text", "Yes/No"], lcd)

    # loads
    jf, fd = [], []
    for name, lc in model.load_cases.items():
        for nl in lc.nodal_loads:
            jf.append([str(nl.node), name, "GLOBAL", nl.fx, nl.fy, nl.fz,
                       nl.mx, nl.my, nl.mz])
        for ml in lc.member_loads:
            if abs(ml.qz) < 1e-12:
                continue
            fd.append([str(ml.member), name, "GLOBAL", "Force", "Gravity",
                       "RelDist", 0, 1, abs(ml.qz), abs(ml.qz)])
    sheet("Joint Loads - Force",
          ["Joint", "LoadPat", "CoordSys", "F1", "F2", "F3", "M1", "M2",
           "M3"], ["Text", "Text", "Text", "N", "N", "N", "N-mm", "N-mm",
                   "N-mm"], jf)
    sheet("Frame Loads - Distributed",
          ["Frame", "LoadPat", "CoordSys", "Type", "Dir", "DistType",
           "RelDistA", "RelDistB", "FOverLA", "FOverLB"],
          ["Text", "Text", "Text", "Text", "Text", "Text", "Unitless",
           "Unitless", "N/mm", "N/mm"], fd)

    # combinations
    cd = []
    for c in model.combinations:
        first = True
        for case, sf in c.factors.items():
            cd.append([c.name, "Linear Add" if first else "", "No",
                       "Linear Static", case, sf])
            first = False
    sheet("Combination Definitions",
          ["ComboName", "ComboType", "AutoDesign", "CaseType", "CaseName",
           "ScaleFactor"],
          ["Text", "Text", "Yes/No", "Text", "Text", "Unitless"], cd)

    wb.save(path)
    return path
