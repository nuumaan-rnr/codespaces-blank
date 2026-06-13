"""Tests for the Design Validation Report and dimensioned model views."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.analysis import run_all
from rack15512.builder import LevelSpec, RackConfig, build_rack
from rack15512.checks.en15512 import run_checks
from rack15512.master_xlsx import load_master
from rack15512.report_html import design_validation_report
from rack15512.viewer import (plot_front_elevation, plot_plan,
                              plot_side_elevation)

MASTER = os.path.join(os.path.dirname(__file__), "..", "examples",
                      "Master.xlsx")
needs_master = pytest.mark.skipif(not os.path.exists(MASTER),
                                  reason="Master.xlsx not present")


def _built():
    mw = load_master(MASTER)
    cfg = RackConfig(module="back-to-back", n_bays=2, depth=1000.0,
                     b2b_gap=250.0,
                     levels=[LevelSpec(1500.0, "RHS 112x50x2.0", 20000.0)] * 2,
                     master=mw, upright_section="UP0016",
                     brace_section="C 36X21X1.5", base_stiffness="auto",
                     include_accidental=False)
    return build_rack(cfg)


@needs_master
def test_base_and_connector_stiffness_in_model():
    m = _built()
    # every support carries a real rotational base spring (not free/fixed)
    assert all(isinstance(s.rx, float) and s.rx > 0 for s in m.supports)
    assert all(isinstance(s.ry, float) and s.ry > 0 for s in m.supports)
    # base moment-resistance table for the partial-restraint check
    assert m.base_plate.m_rd_n
    # beam connectors carry rotational stiffness (semi-rigid)
    beams = [x for x in m.members.values() if x.member_set == "pallet beams"]
    assert beams and all(b.hinge_i.rz and b.hinge_i.rz > 0 for b in beams)


@needs_master
def test_dimensioned_views_render():
    m = _built()
    for fn in (plot_front_elevation, plot_side_elevation, plot_plan):
        fig = fn(m)
        assert fig is not None
        import matplotlib.pyplot as plt
        plt.close(fig)


@needs_master
def test_design_validation_report_contents():
    m = _built()
    cases = run_all(m)
    checks = run_checks(m, cases)
    html = design_validation_report(m, cases, checks,
                                    meta={"project": "P", "engineer": "E"})
    # self-contained: embedded images, no external refs
    assert html.startswith("<!doctype html>")
    assert "data:image/png;base64," in html
    # the four model views are embedded
    for cap in ("Front elevation", "Side elevation", "Plan (top",
                "3D view"):
        assert cap in html
    # EN clauses cited for the checks
    for clause in ("EN 15512 §9.7.6", "EN 1993-1-1 §6.3.1",
                   "EN 1993-1-8 Table 3.4", "§9.10.1",
                   "EN 15512 §10.5.1", "EN 15512 §9.4.5"):
        assert clause in html
    # supports + connector stiffness are documented
    assert "Base / floor connections" in html
    assert "Beam-to-upright connectors" in html
    assert "k_rx [kNm/rad]" in html
    # overall verdict + load combinations
    assert "OVERALL RESULT" in html
    assert "Load cases and combinations" in html


@needs_master
def test_docx_and_pdf_reports(tmp_path):
    docx = pytest.importorskip("docx")
    pytest.importorskip("reportlab")
    from rack15512.report_doc import build_report_blocks, write_reports
    m = _built()
    cases = run_all(m)
    checks = run_checks(m, cases)
    blocks = build_report_blocks(m, cases, checks,
                                 meta={"project": "P", "engineer": "E"})
    kinds = {b[0] for b in blocks}
    assert {"title", "verdict", "h2", "table", "image", "result"} <= kinds
    dp = tmp_path / "r.docx"
    pp = tmp_path / "r.pdf"
    write_reports(m, cases, checks, {"project": "P"},
                  docx_path=str(dp), pdf_path=str(pp))
    assert dp.exists() and dp.stat().st_size > 10000
    assert pp.exists() and pp.read_bytes()[:4] == b"%PDF"
    # DOCX is a valid zip openable by python-docx, with our headings present
    d = docx.Document(str(dp))
    text = "\n".join(p.text for p in d.paragraphs)
    assert "Design Validation Report" in text
    assert any("EN 15512 design verifications" in p.text for p in d.paragraphs)


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
