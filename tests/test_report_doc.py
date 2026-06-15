"""DOCX / PDF report generation smoke tests (skipped if deps missing)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

pytest.importorskip("docx", reason="python-docx not installed")
pytest.importorskip("reportlab", reason="reportlab not installed")

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks
from rack15512.report_doc import write_reports

_META = {"project": "P", "system": "S", "configuration": "C",
         "client": "", "location": "", "engineer": ""}


def test_docx_pdf_generation(tmp_path):
    m = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0], depth=1000.0))
    cases = run_all(m)
    checks = run_checks(m, cases)
    dx, pf = tmp_path / "r.docx", tmp_path / "r.pdf"
    write_reports(m, cases, checks, _META,
                  docx_path=str(dx), pdf_path=str(pf))
    assert dx.exists() and dx.stat().st_size > 1000
    assert pf.exists() and pf.stat().st_size > 1000
