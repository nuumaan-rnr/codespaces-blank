"""Guard against the Windows cp1252 UnicodeEncodeError: every text-mode
open() in the package must specify an explicit encoding (reports contain
Unicode such as Delta, the section sign and <=)."""

import glob
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

PKG = os.path.join(os.path.dirname(__file__), "..", "rack15512")
APP = os.path.join(os.path.dirname(__file__), "..", "app_streamlit.py")

_OPEN = re.compile(r"\bopen\s*\(")


def _text_opens_without_encoding(path):
    bad = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            if not _OPEN.search(line):
                continue
            if '"rb"' in line or '"wb"' in line or "'rb'" in line \
                    or "'wb'" in line:
                continue            # binary mode is fine
            if "encoding=" in line:
                continue            # explicit encoding present
            bad.append((n, line.strip()))
    return bad


def test_all_text_opens_specify_encoding():
    offenders = {}
    for path in glob.glob(os.path.join(PKG, "**", "*.py"), recursive=True) \
            + [APP]:
        bad = _text_opens_without_encoding(path)
        if bad:
            offenders[os.path.relpath(path)] = bad
    assert not offenders, (
        "text-mode open() without encoding= (breaks on Windows cp1252):\n"
        + "\n".join(f"  {f}:{n}: {ln}"
                    for f, items in offenders.items() for n, ln in items))


def test_design_report_is_utf8_roundtrip(tmp_path):
    """A report with Unicode writes and reads back losslessly as UTF-8."""
    master = os.path.join(os.path.dirname(__file__), "..", "examples",
                          "Master.xlsx")
    if not os.path.exists(master):
        import pytest
        pytest.skip("Master.xlsx not present")
    from rack15512.analysis import run_all
    from rack15512.builder import LevelSpec, RackConfig, build_rack
    from rack15512.checks.en15512 import run_checks
    from rack15512.master_xlsx import load_master
    from rack15512.report_html import design_validation_report

    m = build_rack(RackConfig(
        n_bays=1, levels=[LevelSpec(1500.0, "RHS 112x50x2.0", 20000.0)],
        master=load_master(master), upright_section="UP0016",
        brace_section="C 36X21X1.5", base_stiffness="auto",
        include_accidental=False))
    cases = run_all(m)
    html = design_validation_report(m, cases, run_checks(m, cases), meta={})
    p = tmp_path / "r.html"
    p.write_text(html, encoding="utf-8")
    assert "Δ" in html or "§" in html          # contains non-cp1252 chars
    assert p.read_text(encoding="utf-8") == html


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
