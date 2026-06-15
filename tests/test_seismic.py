"""Tests for the IS 1893:2016 seismic modal response-spectrum analysis."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512 import seismic
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks
from rack15512.model import SeismicSettings


def test_design_spectrum_sa_g_per_soil():
    # plateau and decay branches (IS 1893:2016 Cl 6.4.2)
    assert seismic.design_spectrum_sa_g(0.3, "II") == pytest.approx(2.50)
    assert seismic.design_spectrum_sa_g(1.0, "II") == pytest.approx(1.36)
    assert seismic.design_spectrum_sa_g(0.5, "I") == pytest.approx(2.00)
    assert seismic.design_spectrum_sa_g(1.0, "III") == pytest.approx(1.67)
    # short-period rising branch, all soils
    assert seismic.design_spectrum_sa_g(0.05, "III") == pytest.approx(1.75)


def test_horizontal_coefficient_and_zones():
    assert seismic.ZONE_FACTORS == {"II": 0.10, "III": 0.16, "IV": 0.24,
                                    "V": 0.36}
    s = SeismicSettings(zone="IV", importance=1.0, response_reduction=4.0,
                        soil_type="II")
    # Ah = (0.24/2)*(1/4)*2.5 = 0.075 on the plateau
    assert seismic.horizontal_seismic_coefficient(0.3, s) == pytest.approx(
        0.075)


def test_srss_combination():
    s = SeismicSettings(combination="SRSS")
    assert seismic._combine([3.0, 4.0], [0.5, 0.3], s) == pytest.approx(5.0)


def test_seismic_weight_dead_plus_kappa_pallets():
    cfg = RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0], depth=1000.0)
    model = build_rack(cfg)
    s_lo = SeismicSettings(imposed_factor=0.25, include_self_mass=False)
    s_hi = SeismicSettings(imposed_factor=0.75, include_self_mass=False)
    w_lo = sum(seismic._node_weights(model, s_lo).values())
    w_hi = sum(seismic._node_weights(model, s_hi).values())
    assert w_lo > 0 and w_hi > w_lo            # more pallet mass -> heavier
    # self mass adds weight
    s_self = SeismicSettings(imposed_factor=0.25, include_self_mass=True)
    assert sum(seismic._node_weights(model, s_self).values()) > w_lo


def test_seismic_pipeline_produces_cases_and_checks():
    cfg = RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0], depth=1000.0)
    model = build_rack(cfg)
    model.seismic = SeismicSettings(enabled=True, zone="IV", soil_type="II")
    model.combinations = []                     # only run the seismic cases
    from rack15512.analysis import run_all
    cases = run_all(model)
    seis = [c for c in cases if c.kind == "SEISMIC"]
    # 3 factored LSD rows x 2 signs + 1 unfactored 1.0(DL+EL) drift row x 2
    assert len(seis) == 8
    svc = [c for c in seis if c.seismic_service]
    assert len(svc) == 2                          # the 1.0(DL+EL) drift cases
    ss = model.seismic_summary
    assert ss["base_shear_x_kN"] > 0 and ss["fundamental_T"] > 0
    assert ss["captured_mass_x_pct"] >= 50.0
    checks = run_checks(model, cases)
    kinds = {c.check for c in checks}
    assert "SEISMIC_DRIFT" in kinds and "SEISMIC_PDELTA" in kinds
    # higher zone -> larger base shear
    model2 = build_rack(cfg)
    model2.seismic = SeismicSettings(enabled=True, zone="II", soil_type="II")
    model2.combinations = []
    run_all(model2)
    assert model2.seismic_summary["base_shear_x_kN"] \
        < ss["base_shear_x_kN"]


def test_pallet_sliding_caps_base_shear():
    from rack15512.analysis import run_all
    cfg = RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0], depth=1000.0)

    def base_shear(sliding, mu):
        m = build_rack(cfg)
        m.seismic = SeismicSettings(enabled=True, zone="V", soil_type="II",
                                    pallet_sliding=sliding, pallet_mu=mu)
        m.combinations = []
        run_all(m)
        return m.seismic_summary

    off = base_shear(False, 0.05)
    on = base_shear(True, 0.05)            # very low friction -> sliding governs
    assert on["sliding_scale_x"] < 1.0
    assert on["base_shear_x_kN"] < off["base_shear_x_kN"]
    # high friction -> pallet does not slide, no reduction
    hi = base_shear(True, 0.6)
    assert hi["sliding_scale_x"] == 1.0


def test_spine_bracing_reduces_down_aisle_drift():
    base = dict(module="back-to-back", n_bays=2, b2b_gap=250.0,
                beam_levels=[1500.0, 3000.0], depth=1000.0,
                frame_height=3300.0, seismic=True, seismic_zone="IV")

    def max_drift(**extra):
        m = build_rack(RackConfig(**base, **extra))
        m.combinations = []
        from rack15512.analysis import run_all
        checks = run_checks(m, run_all(m))
        return max(c.utilization for c in checks
                   if c.check == "SEISMIC_DRIFT")

    bare = max_drift()
    braced = max_drift(spine_bracing=True, plan_bracing=True)
    assert braced < bare


def test_steel_weight_and_selected_bays():
    from rack15512.builder import _selected_bays
    assert _selected_bays(6, "all") == [0, 1, 2, 3, 4, 5]
    assert _selected_bays(6, "alternate") == [0, 2, 4]
    assert _selected_bays(6, "every_3rd") == [0, 3]
    from rack15512.seismic_study import steel_weight
    m = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0]))
    assert steel_weight(m) > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
