"""Tests for the RFEM per-sheet upright property importer (one section per
sheet, columns Description|Symbol|Value|Unit|Comment) with the axis swap."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.checks.en15512 import _chi_ft
from rack15512.master_xlsx import (load_master, load_upright_properties)
from rack15512.model import Steel

HERE = os.path.dirname(__file__)
RFEM = os.path.join(HERE, "..", "examples", "Upright_Properties.xlsx")
MASTER = os.path.join(HERE, "..", "examples", "Master.xlsx")
needs = pytest.mark.skipif(not os.path.exists(RFEM),
                           reason="examples/Upright_Properties.xlsx not present")


@needs
def test_imports_all_sections_as_uprights():
    mw = load_upright_properties(RFEM)
    assert len(mw.library.sections) == 25
    assert all(s.role == "upright" for s in mw.library.sections.values())
    # auto-detection: plain load_master routes the per-sheet file here too
    assert len(load_master(RFEM).library.sections) == 25


@needs
def test_axis_swap_matches_existing_master():
    # RFEM major axis (Iy) maps to the model's local z; verify against the
    # existing examples/Master.xlsx which already encodes the swap
    new = load_upright_properties(RFEM).library.sections["UP0002"]
    assert abs(new.A - 318.0) < 1.0
    assert abs(new.Iz - 336500.0) < 1.0      # = RFEM Iy (major / down-aisle)
    assert abs(new.Iy - 105900.0) < 1.0      # = RFEM Iz (minor / cross-aisle)
    assert new.Welz > new.Wely               # strong-axis modulus is larger
    if os.path.exists(MASTER):
        old = load_master(MASTER).library.sections["UP0002"]
        assert abs(new.Iy - old.Iy) < 1.0 and abs(new.Iz - old.Iz) < 1.0


@needs
def test_full_property_spectrum_present():
    s = load_upright_properties(RFEM).library.sections["UP0016"]
    # shear areas (Timoshenko), warping + shear centre + torsion (FT buckling)
    assert s.Avy and s.Avz and s.Avy > 0 and s.Avz > 0
    assert s.It_gross and s.Iw_gross and s.y0
    assert s.depth_h and s.width_b            # parsed from the fibre distances
    assert s.buckling_curve_z in ("a0", "a", "b", "c", "d")


@needs
def test_ft_buckling_activates():
    mw = load_upright_properties(RFEM)
    s = mw.library.sections["UP0016"]
    mat = Steel("steel", fy=mw.fy["UP0016"])
    chi = _chi_ft(s, mat, length=3000.0, Ncr_y=1.0e5, beta_T=0.7)
    assert chi is not None and 0.0 < chi <= 1.0   # not skipped


@needs
def test_fy_recovered_from_npl():
    mw = load_upright_properties(RFEM)
    # fy = Npl,d / A, rounded to 5 MPa -> a sensible steel grade
    assert all(200.0 <= fy <= 700.0 for fy in mw.fy.values())
    assert abs(mw.fy["UP0002"] - 355.0) < 1e-6
