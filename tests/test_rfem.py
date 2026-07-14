"""Tests for the RFEM importer and the validation against the SPR
reference model's exported results."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.combos import assemble, apply_ehf
from rack15512.engine.opensees import OpenSeesEngine
from rack15512.master_xlsx import load_master
from rack15512.model import DIRECTION_VECTORS, Combination
from rack15512.rfem_compare import (MemberRef, comparison_rows, compare_results,
                                    coverage, export_co_map,
                                    governing_by_section, read_rfem_results,
                                    section_gov_rows, write_comparison_workbook)
from rack15512.rfem_import import load_rfem

HERE = os.path.dirname(__file__)
DATA = os.path.join(HERE, "..", "examples", "SPR_CHECK_Data.xlsx")
MASTER = os.path.join(HERE, "..", "examples", "Master.xlsx")
needs_data = pytest.mark.skipif(not os.path.exists(DATA),
                                reason="SPR_CHECK_Data.xlsx not present")

# the importer splits member 711 for its concentrated load; its station
# extremes are no longer comparable 1:1 with the RFEM full-length member
SPLIT = (711, 529)


@pytest.fixture(scope="module")
def model():
    return load_rfem(DATA)


@needs_data
def test_rfem_import_structure(model):
    assert len(model.supports) == 16
    assert len(model.members) == 529          # 528 + 1 split
    assert model.imperfection.value() == pytest.approx(1.0 / 300.0)
    beams = [m for m in model.members.values() if m.hinge_i]
    assert len(beams) == 60
    assert beams[0].hinge_i.rz == pytest.approx(6573.0 * 1e4)
    trusses = [m for m in model.members.values() if m.mtype == "truss"]
    assert len(trusses) == 176
    # pinned bases in the export (nonlinear springs are not exported)
    assert model.supports[0].ry is False
    # Z flipped to Z-up
    assert min(n.z for n in model.nodes.values()) == 0.0
    assert max(n.z for n in model.nodes.values()) == pytest.approx(9050.0, abs=1.0)
    # self weight rebuilt from material density (RFEM total: 12.09 kN)
    lc1 = model.load_cases["LC1"]
    tot = sum(abs(ml.qz) * model.member_length(model.members[ml.member])
              for ml in lc1.member_loads)
    assert tot == pytest.approx(12.09e3, rel=0.01)
    # combinations with per-combo imperfection senses
    co1 = next(c for c in model.combinations if c.name.startswith("CO1 "))
    assert co1.imp_directions == ["+x"]
    co4 = next(c for c in model.combinations if c.name.startswith("CO4 "))
    assert co4.imp_directions == ["+y"]


@needs_data
def test_rfem_linear_lc2_matches(model):
    """RFEM solves load cases linearly; our first-order LC2 member forces
    must reproduce the export (validates geometry, hinges, supports,
    sections and loads in one shot)."""
    ref = {}
    import openpyxl
    wb = openpyxl.load_workbook(DATA, data_only=True, read_only=True)
    sheet = next(s for s in wb.sheetnames if s.startswith("LC2 - 4.1"))
    cur = None
    for r in wb[sheet].iter_rows(min_row=3, values_only=True):
        head = "" if r[0] is None else str(r[0]).strip()
        if head.isdigit():
            cur = ref.setdefault(int(head), MemberRef())
        if cur is None or r[3] is None:
            continue
        try:
            N, My, Mz = float(r[3]) * 1e3, float(r[7]) * 1e4, float(r[8]) * 1e4
        except (TypeError, ValueError):
            continue
        cur.N_min = min(cur.N_min, N)
        cur.N_max = max(cur.N_max, N)
        cur.Mz_absmax = max(cur.Mz_absmax, abs(My))
        cur.My_absmax = max(cur.My_absmax, abs(Mz))

    case = OpenSeesEngine().run_case(
        model, assemble(model, Combination("LC2", "SLS", {"LC2": 1.0})),
        name="LC2", combo="LC2", kind="SLS", order=1)
    assert case.converged
    comps = compare_results(model, [case], {"LC2": ref}, skip_members=SPLIT)
    diffs = sorted(c.rel_diff for c in comps)
    assert len(comps) > 300
    assert diffs[len(diffs) // 2] < 0.02          # median < 2%


@needs_data
def test_rfem_second_order_with_base_springs_matches():
    """The reference model's nonlinear combinations only reproduce when the
    load-dependent floor-connection springs from the master are restored;
    CO1 member forces then match RFEM's second-order results."""
    master = load_master(MASTER)
    model = load_rfem(DATA, master=master)
    assert isinstance(model.supports[0].ry, float)   # spring recovered
    rfem = read_rfem_results(DATA)
    combo = next(c for c in model.combinations if c.name.startswith("CO1 "))
    loads = apply_ehf(model, assemble(model, combo),
                      model.imperfection.value(), DIRECTION_VECTORS["+x"])
    case = OpenSeesEngine().run_case(model, loads, name="CO1", combo="CO1",
                                     kind="ULS", order=2, imp_direction="+x")
    assert case.converged
    comps = compare_results(model, [case], {"CO1": rfem["CO1"]},
                            skip_members=SPLIT)
    mo = sorted(c.rel_diff for c in comps if not c.quantity.startswith("N"))
    ax = sorted(c.rel_diff for c in comps if c.quantity.startswith("N"))
    assert ax[len(ax) // 2] < 0.01                # axials median < 1%
    assert mo[len(mo) // 2] < 0.03                # moments median < 3%


@needs_data
def test_rfem_governing_by_section_and_rows(model, tmp_path):
    """The per-section governing summary and the flat UI rows are derived from
    the same comparisons and stay consistent with them."""
    ref = read_rfem_results(DATA)          # CO<n> result sheets only
    co = next(iter(ref))
    # a converged case whose combo id matches a result combination; absolute
    # accuracy is covered elsewhere, this test checks summary consistency
    case = OpenSeesEngine().run_case(
        model, assemble(model, Combination("LC2", "SLS", {"LC2": 1.0})),
        name=co, combo=co, kind="SLS", order=1)
    comps = compare_results(model, [case], {co: ref[co]}, skip_members=SPLIT)
    assert comps

    govs = governing_by_section(model, comps)
    assert govs
    # one governing pick per (section, quantity), and it is the app-worst
    for g in govs:
        peers = [c for c in comps
                 if model.members[c.member].section == g.section
                 and c.quantity == g.quantity]
        assert abs(g.ours) == max(abs(c.ours) for c in peers)
    assert len({(g.section, g.quantity) for g in govs}) == len(govs)

    rows = comparison_rows(comps)
    assert len(rows) == len(comps)
    assert set(rows[0]) >= {"combination", "member", "ours", "RSTAB",
                            "rel diff %"}
    srows = section_gov_rows(govs)
    assert len(srows) == len(govs)

    cov = coverage(model, [case], ref)
    assert co in cov["matched_combos"]

    out = str(tmp_path / "cmp.xlsx")
    write_comparison_workbook(model, [case], {co: ref[co]}, out,
                              skip_members=SPLIT)
    import openpyxl
    wb = openpyxl.load_workbook(out, read_only=True)
    assert "Governing per section" in wb.sheetnames
    assert "All members x combos" in wb.sheetnames


@needs_data
def test_export_co_map_matches_workbook(model, tmp_path):
    """When the RSTAB results file is this app's own export, an app case maps
    to the exact CO id the exporter wrote in the 2.5 Load Combinations sheet."""
    import openpyxl
    from rack15512.export_solvers import _combo_rows, to_rstab8_xlsx
    from rack15512.results import CaseResult

    p = str(tmp_path / "exp.xlsx")
    to_rstab8_xlsx(model, p)
    wb = openpyxl.load_workbook(p, data_only=True, read_only=True)
    written = {}
    for r in wb["2.5 Load Combinations"].iter_rows(min_row=3, values_only=True):
        if r[0] and str(r[0]).startswith("CO"):
            written[str(r[0])] = str(r[2])         # col C = description

    resolve = export_co_map(model)
    rows = _combo_rows(model)
    assert len(written) == len(rows)
    for i, row in enumerate(rows):
        co = f"CO{i + 1}"
        assert written[co] == row["name"]
        # a synthetic app case exactly as analysis.run_all names them
        case = CaseResult(name=row["name"], combo=row["combo"],
                          kind=row["kind"], order=2,
                          imp_direction=row["imp"] or "", converged=True)
        assert resolve(case) == co


def test_read_rfem_results_detects_moment_unit(tmp_path):
    """A results workbook in RSTAB factory units (moments kNm) and one in the
    company cm profile (moments kNcm) must both import to the same base N*mm -
    the unit is read from the group header, not assumed (a 100x scale bug
    otherwise: kNm read as kNcm)."""
    import openpyxl

    def make(path, moment_unit):
        wb = openpyxl.Workbook()
        wb.remove(wb.active)
        ws = wb.create_sheet("CO1 - 4.1 Members - Internal Fo"[:31])
        ws.append(["Member", "Node", "Location", "Forces [kN]", None, None,
                   f"Moments [{moment_unit}]", None, None, None])
        ws.append(["No.", "No.", "x [mm]", "N", "Vy", "Vz", "MT", "My", "Mz",
                   "Cross-Section"])
        ws.append([1, 100, 0, -10.0, 0, 0, 0, 5.0, 2.0, "UP"])
        wb.save(path)

    pm, pc = str(tmp_path / "knm.xlsx"), str(tmp_path / "kncm.xlsx")
    make(pm, "kNm")
    make(pc, "kNcm")
    rm = read_rfem_results(pm)["CO1"][1]
    rc = read_rfem_results(pc)["CO1"][1]

    assert rm.N_min == pytest.approx(-10.0e3)          # kN -> N (both files)
    # My (sheet) -> our Mz: 5 kNm = 5e6 N*mm, 5 kNcm = 5e4 N*mm
    assert rm.Mz_absmax == pytest.approx(5.0e6)
    assert rc.Mz_absmax == pytest.approx(5.0e4)
    assert rm.Mz_absmax == pytest.approx(100.0 * rc.Mz_absmax)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))


def test_rfem_import_coupling_members_and_base_stiffness(tmp_path):
    # RSTAB 'Coupling' members (rigid/hinge links, no cross-section) must not
    # crash the importer; they become a stiff COUPLING beam with a moment
    # release at the Hinge end.  A supplied base_stiffness fills the free base
    # rotation that RSTAB omits from the Excel export.
    import openpyxl
    from rack15512.rfem_import import load_rfem

    wb = openpyxl.Workbook()
    def sheet(name, header, rows):
        ws = wb.create_sheet(name)
        ws.append(["h"] * len(header[0]))          # row 1 (group headers)
        ws.append(header[1])                        # row 2 (column headers)
        for r in rows:
            ws.append(r)
    wb.remove(wb.active)
    sheet("1.1 Nodes",
          [[], ["No.", "Ref", "Sys", "X", "Y", "Z", "C"]],
          [[1, 0, "Cartesian", 0, 0, 0, ""],
           [2, 0, "Cartesian", 0, 0, -1000, ""],
           [3, 0, "Cartesian", 0, 0, -1031, ""]])   # 31 mm above node 2
    sheet("1.2 Materials",
          [[], ["No.", "Desc", "E", "G", "n", "g", "a", "gM", "Model", "C"]],
          [[1, "Steel", 20000, 7690, 0.3, 78.5, 1.2e-5, 1.0, "Elastic", ""]])
    sheet("1.3 Cross-Sections ",
          [[], ["No.", "Desc", "Matl", "J", "Iy", "Iz", "A", "Ay", "Az",
                "a", "a'", "b", "h", "C"]],
          [[1, "UP", 1, 20.0, 150.0, 350.0, 3.5, 1.0, 1.0, 0, 0, 63, 90, ""]])
    sheet("1.4 Member Hinges",
          [[], ["No.", "Sys", "ux", "uy", "uz", "jx", "jy", "jz", "C"]], [])
    sheet("1.7 Members",
          [[], ["No.", "Type", "Start", "End", "RotType", "b", "CSs", "CSe",
                "Hs", "He", "Ecc", "Div", "Shape", "L", "W", "", "C"]],
          [[1, "Beam", 1, 2, "Angle", 0, 1, 1, 0, 0, 0, 0, "", 1000, 1, "Z", ""],
           [2, "Coupling Rigid-Hinge", 2, 3, "", 0, None, None, None, None,
            0, 0, "", 31, 0, "", ""]])
    sheet("1.8 Nodal Supports",
          [[], ["No.", "Nodes", "Seq", "aX", "aY", "aZ", "inZ",
                "uX", "uY", "uZ", "jX", "jY", "jZ", "C"]],
          [[1, "1", "XYZ", 0, 0, 0, "-", "+", "+", "+", "-", "0", "+",
            "UP-BASE"]])
    p = str(tmp_path / "coupling.xlsx")
    wb.save(p)

    m = load_rfem(p, fy=355.0, base_stiffness=5.0e7)
    # coupling imported as a stiff COUPLING beam with a moment release (pin) at
    # the Hinge (end) node
    coup = [mm for mm in m.members.values() if mm.member_set == "coupling"]
    assert len(coup) == 1
    c = coup[0]
    assert c.section == "COUPLING" and c.hinge_i is None
    assert c.hinge_j is not None and c.hinge_j.rz == 0.0     # pinned end
    assert "COUPLING" in m.sections and m.sections["COUPLING"].A >= 1.0e4
    # base stiffness filled the free base rotation
    base = m.supports[0]
    assert base.ry == 5.0e7
