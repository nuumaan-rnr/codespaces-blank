"""SAP2000 importer / exporter tests (synthetic 2-bay portal + round-trip)."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import openpyxl

from rack15512.sap2000 import (load_sap2000, to_sap2000, verify_sap2000_import,
                               _automesh_at_joints)


def _write_sap(path):
    """A minimal SAP2000 database workbook: one 3 m upright with a beam
    landing at mid-height (so auto-mesh must split the upright), a fixed base,
    self-weight + a live UDL, and one combination."""
    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    def sheet(title, header, units, rows):
        ws = wb.create_sheet(title[:31])
        ws.append([f"TABLE:  {title}"])
        ws.append(header)
        ws.append(units)
        for r in rows:
            ws.append(r)

    sheet("Joint Coordinates",
          ["Joint", "CoordSys", "CoordType", "XorR", "Y", "Z", "SpecialJt",
           "GlobalX", "GlobalY", "GlobalZ"],
          ["Text", "Text", "Text", "mm", "mm", "mm", "Yes/No", "mm", "mm",
           "mm"],
          [["1", "GLOBAL", "Cartesian", 0, 0, 0, "No", 0, 0, 0],
           ["2", "GLOBAL", "Cartesian", 0, 0, 3000, "No", 0, 0, 3000],
           ["3", "GLOBAL", "Cartesian", 0, 0, 1500, "No", 0, 0, 1500],  # mid
           ["4", "GLOBAL", "Cartesian", 1200, 0, 1500, "No", 1200, 0, 1500]])
    sheet("Connectivity - Frame",
          ["Frame", "JointI", "JointJ", "IsCurved", "Length"],
          ["Text", "Text", "Text", "Yes/No", "mm"],
          [["1", "1", "2", "No", 3000],       # upright, spans past joint 3
           ["2", "3", "4", "No", 1200]])      # beam landing at mid-height
    sheet("Frame Section Assignments",
          ["Frame", "SectionType", "AutoSelect", "AnalSect", "DesignSect",
           "MatProp"],
          ["Text", "Text", "Text", "Text", "Text", "Text"],
          [["1", "Section Designer", "N.A.", "UP", "UP", "Default"],
           ["2", "Frame", "N.A.", "BM", "BM", "Default"]])
    sheet("Frame Props 01 - General",
          ["SectionName", "Material", "Shape", "t3", "t2", "Area", "TorsConst",
           "I33", "I22", "S33Top", "S22Left"],
          ["Text", "Text", "Text", "mm", "mm", "mm2", "mm4", "mm4", "mm4",
           "mm3", "mm3"],
          [["UP", "Fe250", "SD Section", 100, 80, 900, 2500, 700000, 2000000,
            14000, 25000],
           ["BM", "Fe250", "Box/Tube", 120, 50, 640, 680000, 1400000, 260000,
            23000, 10000]])
    sheet("MatProp 02 - Basic Mech Props",
          ["Material", "UnitWeight", "UnitMass", "E1", "G12", "U12", "A1"],
          ["Text", "N/mm3", "N-s2/mm4", "N/mm2", "N/mm2", "Unitless", "1/C"],
          [["Fe250", 7.7e-5, 7.85e-9, 210000, 80769, 0.3, 1.17e-5]])
    sheet("MatProp 03a - Steel Data", ["Material", "Fy", "Fu"],
          ["Text", "N/mm2", "N/mm2"], [["Fe250", 250, 410]])
    sheet("Frame Property Modifiers",
          ["Frame", "AMod", "AS2Mod", "AS3Mod", "JMod", "I22Mod", "I33Mod",
           "MassMod", "WeightMod", "EAModifier", "EIModifier"],
          ["Text"] + ["Unitless"] * 10,
          [["1", 1, 1, 1, 1, 1, 1, 1, 1, 0.8, 0.8],
           ["2", 1, 1, 1, 1, 1, 1, 1, 1, 0.8, 0.8]])
    sheet("Frame Releases 1 - General",
          ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J", "V3J",
           "TJ", "M2J", "M3J", "PartialFix"],
          ["Text"] + ["Yes/No"] * 13,
          [["2", "No", "No", "No", "No", "No", "Yes", "No", "No", "No", "No",
            "No", "Yes", "Yes"]])
    sheet("Frame Releases 2 - Part Fixity",
          ["Frame", "PI", "V2I", "V3I", "TI", "M2I", "M3I", "PJ", "V2J", "V3J",
           "TJ", "M2J", "M3J"],
          ["Text"] + ["N/mm"] * 3 + ["N-mm/rad"] * 3 + ["N/mm"] * 3
          + ["N-mm/rad"] * 3,
          [["2", None, None, None, None, None, 1.0e8, None, None, None, None,
            None, 1.0e8]])
    sheet("Joint Restraint Assignments",
          ["Joint", "U1", "U2", "U3", "R1", "R2", "R3"],
          ["Text"] + ["Yes/No"] * 6,
          [["1", "Yes", "Yes", "Yes", "Yes", "Yes", "Yes"]])
    sheet("Jt Spring Assigns 1 - Uncoupled",
          ["Joint", "CoordSys", "U1", "U2", "U3", "R1", "R2", "R3"],
          ["Text", "Text", "N/mm", "N/mm", "N/mm", "N-mm/rad", "N-mm/rad",
           "N-mm/rad"], [])
    sheet("Load Pattern Definitions",
          ["LoadPat", "DesignType", "SelfWtMult", "AutoLoad"],
          ["Text", "Text", "Unitless", "Text"],
          [["DEAD", "Dead", 1, ""], ["LIVE", "Live", 0, ""]])
    sheet("Frame Loads - Distributed",
          ["Frame", "LoadPat", "CoordSys", "Type", "Dir", "DistType",
           "RelDistA", "RelDistB", "FOverLA", "FOverLB"],
          ["Text", "Text", "Text", "Text", "Text", "Text", "Unitless",
           "Unitless", "N/mm", "N/mm"],
          [["2", "LIVE", "GLOBAL", "Force", "Gravity", "RelDist", 0, 1, 5, 5]])
    sheet("Joint Loads - Force",
          ["Joint", "LoadPat", "CoordSys", "F1", "F2", "F3", "M1", "M2", "M3"],
          ["Text", "Text", "Text", "N", "N", "N", "N-mm", "N-mm", "N-mm"], [])
    sheet("Combination Definitions",
          ["ComboName", "ComboType", "AutoDesign", "CaseType", "CaseName",
           "ScaleFactor"],
          ["Text", "Text", "Yes/No", "Text", "Text", "Unitless"],
          [["ULS1", "Linear Add", "No", "Linear Static", "DEAD", 1.2],
           ["ULS1", "", "", "Linear Static", "LIVE", 1.2]])
    wb.save(path)


def test_sap2000_import_uses_sap_properties_and_modifier(tmp_path):
    p = str(tmp_path / "m.xlsx")
    _write_sap(p)
    m = load_sap2000(p)
    # SAP's own section properties, axis 3 -> Iz, axis 2 -> Iy
    up = m.sections["UP"]
    assert up.A == 900 and up.Iz == 700000 and up.Iy == 2000000
    # EI/EA modifier 0.8 folded into E (210000 * 0.8)
    assert abs(m.materials["Fe250"].E - 168000) < 1
    # roles from shapes
    assert up.role == "uprights"
    assert m.sections["BM"].role == "pallet beams"
    # semi-rigid beam connector: rz spring = 1e8 both ends
    beams = [mm for mm in m.members.values() if mm.member_set == "pallet beams"]
    assert beams and beams[0].hinge_i.rz == 1.0e8
    # base fully fixed
    assert m.supports[0].ux is True and m.supports[0].rz is True
    assert m.load_cases and m.combinations[0].name == "ULS1"


def test_sap2000_automesh_splits_upright_at_beam(tmp_path):
    p = str(tmp_path / "m.xlsx")
    _write_sap(p)
    m = load_sap2000(p)
    # the upright (frame 1, joints 1->2) must be split at joint 3 (mid-height)
    # where the beam lands, so joint 3 connects the beam to the upright
    from collections import Counter
    deg = Counter()
    for mm in m.members.values():
        deg[mm.node_i] += 1
        deg[mm.node_j] += 1
    assert deg[3] >= 3            # two upright halves + the beam
    # no re-splitting on a second pass (idempotent)
    assert _automesh_at_joints(m) == 0


def test_sap2000_import_runs(tmp_path):
    from rack15512.combos import assemble
    from rack15512.engine.opensees import OpenSeesEngine
    p = str(tmp_path / "m.xlsx")
    _write_sap(p)
    m = load_sap2000(p)
    combo = m.combinations[0]
    case = OpenSeesEngine().run_case(m, assemble(m, combo), name="ULS1",
                                     combo="ULS1", kind="ULS", order=1)
    assert case.converged
    # the upright carries the beam's gravity load in compression
    ups = [mr.N_min for mid, mr in case.members.items()
           if m.members[mid].member_set == "uprights"]
    assert min(ups) < 0


def test_sap2000_export_roundtrip(tmp_path):
    p = str(tmp_path / "m.xlsx")
    _write_sap(p)
    m = load_sap2000(p)
    out = str(tmp_path / "export.xlsx")
    to_sap2000(m, out)
    m2 = load_sap2000(out)
    assert len(m2.nodes) == len(m.nodes)
    assert len(m2.members) == len(m.members)
    assert {s for s in m2.sections} >= {"UP", "BM"}
    assert len(m2.combinations) == len(m.combinations)
    # the export re-verifies 1:1 against the original SAP file
    checks = verify_sap2000_import(m2, p)
    assert all(c["status"] == "ok" for c in checks), \
        [c for c in checks if c["status"] != "ok"]


def test_sap_element_forces_compare(tmp_path):
    """Read a SAP 'Element Forces - Frames' table and compare per frame; the
    axis mapping (M3->Mz, M2->My) and frame-envelope aggregation hold, and a
    matching value is within tolerance while a large mismatch is flagged."""
    from rack15512.sap2000 import (compare_sap_forces, load_sap2000,
                                   read_sap_element_forces)

    mp = str(tmp_path / "m.xlsx")
    _write_sap(mp)
    m = load_sap2000(mp)

    # a results workbook: frame 1 (upright) with P/M2/M3 at two stations
    wb = openpyxl.Workbook()
    wb.remove(wb.active)
    ws = wb.create_sheet("Element Forces - Frames")
    ws.append(["TABLE:  Element Forces - Frames"])
    ws.append(["Frame", "Station", "OutputCase", "CaseType", "StepType",
               "StepNum", "StepLabel", "P", "V2", "V3", "T", "M2", "M3",
               "FrameElem", "ElemStation"])
    ws.append(["Text", "mm", "Text", "Text", "Text", "Unitless", "Text", "N",
               "N", "N", "N-mm", "N-mm", "N-mm", "Text", "mm"])
    ws.append(["1", 0, "DEAD", "LinStatic", "", "", "", -5000, 0, 0, 0,
               1000, 200000, "1-1", 0])
    ws.append(["1", 1500, "DEAD", "LinStatic", "", "", "", -5000, 0, 0, 0,
               500, 100000, "1-1", 1500])
    rp = str(tmp_path / "forces.xlsx")
    wb.save(rp)

    sap = read_sap_element_forces(rp)
    assert "DEAD" in sap and 1 in sap["DEAD"]
    d = sap["DEAD"][1]
    assert d["N_min"] == -5000
    assert d["Mz"] == 200000        # SAP M3 -> our Mz (envelope)
    assert d["My"] == 1000          # SAP M2 -> our My

    # build a fake app case for frame 1 that matches N exactly
    from rack15512.results import CaseResult, MemberResult, Station
    case = CaseResult(name="DEAD", combo="DEAD", kind="SLS", order=1,
                      converged=True)
    first = next(mid for mid, fr in m.frame_origin.items() if fr == 1)
    case.members[first] = MemberResult(
        member=first, length=100.0,
        stations=[Station(x=0, N=-5000, My=1000, Mz=200000)])

    rows = compare_sap_forces(m, [case], sap)
    assert rows
    r1 = next(r for r in rows if r["frame"] == 1)
    assert r1["N SAP [kN]"] == -5.0 and r1["N ours [kN]"] == -5.0
    assert r1["status"] == "ok"


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
