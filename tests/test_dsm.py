"""Validation of the Direct Strength Method engine and the CUFSM interface.

The DSM checks are hand-traceable: boundary continuity of the AISI S100-16
curves, reduction to the gross squash load when nothing buckles, and one fully
worked column whose governing strength is computed by hand in the docstring.
"""

from __future__ import annotations

import math
import os
import tempfile

import pytest

from rack15512 import dsm, cufsm
from rack15512.model import CrossSection, Steel


# --------------------------------------------------------------------- DSM column
def test_no_buckling_returns_squash_load():
    """Huge elastic loads -> no reduction, Pn = Py."""
    r = dsm.column_strength(Py=100.0, Pcre=1e30, Pcrl=1e30, Pcrd=1e30)
    assert r.Pn == pytest.approx(100.0)
    assert r.governs == "global"          # Pne == Py, ties resolve to global


def test_global_curve_continuous_at_lambda_1p5():
    """The two E2.1 branches (0.658^lam^2 and 0.877/lam^2) meet at lambda_c=1.5
    to engineering precision (~0.04% - the AISC/AISI column curve is built that
    way), so Pne has no practical step across the transition."""
    Py = 100.0
    Pcre = Py / 1.5 ** 2                   # lambda_c = 1.5 exactly
    below = dsm._pne(Py, Pcre * 1.0000001)
    above = dsm._pne(Py, Pcre * 0.9999999)
    assert below == pytest.approx(above, rel=1e-3)
    assert dsm._pne(Py, Pcre) == pytest.approx(0.877 / 1.5 ** 2 * Py, rel=1e-3)


def test_local_boundary_no_reduction_below_0776():
    """lambda_l <= 0.776 -> Pnl = Pne (E3.2)."""
    Pne = 100.0
    Pcrl = Pne / 0.5 ** 2                  # lambda_l = 0.5
    assert dsm._pnl(Pne, Pcrl, Pynet=1e30) == pytest.approx(Pne)


def test_distortional_boundary_no_reduction_below_0561():
    """lambda_d <= 0.561 -> Pnd = Py (E4.2)."""
    Py = 100.0
    Pcrd = Py / 0.5 ** 2                   # lambda_d = 0.5
    assert dsm._pnd(Py, Pcrd, Pynet=Py) == pytest.approx(Py)


def test_worked_column_local_governs():
    """Py=200, Pcre=250, Pcrl=150, Pcrd=180 kN (no holes).

    By hand (AISI S100-16):
      lambda_c = sqrt(200/250) = 0.8944 -> Pne = 0.658^0.8 * 200 = 143.08 kN
      lambda_l = sqrt(143.08/150) = 0.977 -> Pnl = 123.5 kN  (governs)
      lambda_d = sqrt(200/180) = 1.054 -> Pnd = 143.7 kN
      Pn = 123.5 kN, local buckling governs.
    """
    r = dsm.column_strength(Py=200e3, Pcre=250e3, Pcrl=150e3, Pcrd=180e3)
    assert r.Pne == pytest.approx(143.08e3, rel=2e-3)
    assert r.Pnl == pytest.approx(123.5e3, rel=3e-3)
    assert r.Pnd == pytest.approx(143.7e3, rel=3e-3)
    assert r.Pn == pytest.approx(123.5e3, rel=3e-3)
    assert r.governs == "local"


def test_perforated_distortional_nets_to_net_yield():
    """With holes and a stocky distortional mode, Pnd -> net-section yield."""
    Py, Pynet = 100.0, 80.0
    r = dsm._pnd(Py, Pcrd=1e30, Pynet=Pynet)   # lambda_d -> 0
    assert r == pytest.approx(Pynet)


def test_holes_never_exceed_net_section_yield():
    """The governing strength of a perforated column cannot exceed Anet*Fy."""
    r = dsm.column_strength(Py=200e3, Pcre=1e30, Pcrl=1e30, Pcrd=1e30,
                            Pynet=150e3)
    assert r.Pn <= 150e3 + 1.0


def test_effective_area_reduces_with_local_buckling():
    """A slender section's DSM effective area is below the gross area, and a
    stocky one recovers the gross area."""
    fy, Ag = 450.0, 600.0
    stocky = dsm.effective_area(fy, Ag, Pcrl=1e30, Pcrd=1e30)
    slender = dsm.effective_area(fy, Ag, Pcrl=0.5 * Ag * fy, Pcrd=0.6 * Ag * fy)
    assert stocky == pytest.approx(Ag)
    assert slender < Ag


# ----------------------------------------------------------------------- DSM beam
def test_beam_global_full_yield_when_stocky():
    """Mcre > 2.78 My -> Mne = My (F2.1)."""
    My = 50.0
    assert dsm._mne(My, Mcre=3.0 * My) == pytest.approx(My)


def test_beam_local_and_distortional_boundaries():
    My = 50.0
    Mne = 50.0
    # local: lambda_l <= 0.776 -> Mnl = Mne
    assert dsm._mnl(Mne, Mcrl=Mne / 0.5 ** 2, Mynet=1e30) == pytest.approx(Mne)
    # distortional: lambda_d <= 0.673 -> Mnd = My
    assert dsm._mnd(My, Mcrd=My / 0.5 ** 2, Mynet=My) == pytest.approx(My)


def test_beam_strength_governs_min():
    r = dsm.beam_strength(My=50e6, Mcre=200e6, Mcrl=40e6, Mcrd=60e6)
    assert r.Mn == min(r.Mne, r.Mnl, r.Mnd)
    assert r.governs in ("global", "local", "distortional")


# -------------------------------------------------------------------- CUFSM curve
def _synthetic_signature():
    """A signature curve with a local (hw=50) and distortional (hw=400) dip,
    then the global branch descending at long half-wavelength."""
    hw = [20, 50, 100, 200, 400, 600, 800, 1600]
    val = [2.0, 0.9, 1.5, 1.3, 1.1, 1.25, 0.8, 0.4]
    return hw, val


def test_signature_minima_finds_local_and_distortional():
    hw, val = _synthetic_signature()
    minima = cufsm.signature_minima(hw, val)
    assert [m[0] for m in minima] == [50, 400]
    local, dist = cufsm.classify_minima(minima)
    assert local[0] == 50 and dist[0] == 400


def test_loads_from_signature_scales_by_reference():
    hw, val = _synthetic_signature()
    loads = cufsm.loads_from_signature(hw, val, reference=100e3)
    assert loads.Pcrl == pytest.approx(0.9 * 100e3)
    assert loads.Pcrd == pytest.approx(1.1 * 100e3)
    assert loads.half_wavelength_local == 50


def test_loads_from_signature_requires_a_minimum():
    with pytest.raises(ValueError):
        cufsm.loads_from_signature([10, 20, 30], [5, 4, 3])   # monotonic


def test_read_signature_csv_roundtrip():
    hw, val = _synthetic_signature()
    fd, path = tempfile.mkstemp(suffix=".csv")
    try:
        with os.fdopen(fd, "w") as fh:
            fh.write("half_wavelength_mm,Pcr_N\n")
            for h, v in zip(hw, val):
                fh.write(f"{h},{v}\n")
        rhw, rval = cufsm.read_signature_csv(path)
        assert rhw == [float(h) for h in hw]
        assert rval == pytest.approx(val)
    finally:
        os.remove(path)


def test_dsm_check_runs_in_pipeline_and_is_opt_in():
    """A section carrying CUFSM data gets a DSM_BC check in the full pipeline;
    a model without it is unaffected (opt-in, no behaviour change)."""
    from rack15512.builder import RackConfig, build_rack
    from rack15512.analysis import run_all
    from rack15512.checks.en15512 import run_checks
    from rack15512.model import DSMData

    model = build_rack(RackConfig(n_bays=1, beam_levels=[1800.0]))
    upright_secs = {model.section_of(m).name for m in model.members.values()
                    if m.member_set == "uprights"}
    assert upright_secs
    for name in upright_secs:
        s = model.sections[name]
        Py = s.A * model.materials[s.material].fy
        s.dsm = DSMData(Pcrl=1.6 * Py, Pcrd=2.0 * Py)   # moderate slenderness
    checks = run_checks(model, run_all(model))
    dsm_checks = [c for c in checks if c.check == "DSM_BC"]
    assert dsm_checks
    assert all(c.member_set == "uprights" for c in dsm_checks)
    assert all(c.utilization > 0.0 for c in dsm_checks)
    assert all("Pn=" in c.detail and "governs" in c.detail for c in dsm_checks)

    plain = build_rack(RackConfig(n_bays=1, beam_levels=[1800.0]))
    assert not [c for c in run_checks(plain, run_all(plain))
                if c.check == "DSM_BC"]


def test_dsm_data_survives_json_roundtrip(tmp_path):
    from rack15512.builder import RackConfig, build_rack
    from rack15512.model import DSMData
    from rack15512 import io_json

    model = build_rack(RackConfig(n_bays=1, beam_levels=[1800.0]))
    name = next(model.section_of(m).name for m in model.members.values()
               if m.member_set == "uprights")
    model.sections[name].dsm = DSMData(Pcrl=1.0e6, Pcrd=1.2e6, Anet=540.0)
    p = tmp_path / "m.json"
    io_json.save(model, str(p))
    back = io_json.load(str(p))
    d = back.sections[name].dsm
    assert isinstance(d, DSMData)
    assert d.Pcrl == 1.0e6 and d.Pcrd == 1.2e6 and d.Anet == 540.0


def test_populate_effective_properties_feeds_en_checks():
    """A CUFSM run fills A_eff so the EN 15512 effective-section checks use
    DSM-derived properties; a stocky section keeps the gross area."""
    steel = Steel("S450GD", fy=450.0)
    sec = CrossSection(name="UP100", material="S450GD", A=600.0,
                       Iy=1.0e6, Iz=1.0e6, J=1.0e3, Wely=2.0e4, Welz=2.0e4)
    Py = sec.A * steel.fy
    slender = cufsm.BucklingLoads(Pcrl=0.5 * Py, Pcrd=0.6 * Py)
    cufsm.populate_effective_properties(sec, steel, slender)
    assert sec.A_eff is not None and sec.A_eff < sec.A
    # existing value is respected unless overwrite is requested
    sec.A_eff = 590.0
    cufsm.populate_effective_properties(sec, steel, slender)
    assert sec.A_eff == 590.0
    cufsm.populate_effective_properties(sec, steel, slender, overwrite=True)
    assert sec.A_eff < 590.0
