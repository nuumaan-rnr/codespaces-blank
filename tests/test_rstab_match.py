"""RSTAB-matching config options: EN1993 imperfection, connector override,
nonlinear axial-dependent base."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rack15512.builder import RackConfig, build_rack, LevelSpec
from rack15512.engine.opensees import OpenSeesEngine
from rack15512.model import Imperfection


def test_en1993_imperfection_is_flat_phi_s():
    imp = Imperfection(n_cols=4, phi_s=1/300, standard="EN1993", phi_min=1/500)
    assert abs(imp.value() - 1/300) < 1e-9          # flat, no 2x / sqrt factor
    imp15 = Imperfection(n_cols=4, phi_s=1/300, standard="EN15512", phi_l=0)
    assert imp15.value() > imp.value()              # EN 15512 is larger (amplified)


def test_connector_override_applied():
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, connector_stiffness_override=73.0e6))
    beams = [mm for mm in m.members.values() if mm.member_set == "pallet beams"]
    assert beams and all(b.hinge_i.rz == 73.0e6 and b.hinge_j.rz == 73.0e6 for b in beams)


def test_base_table_interp_and_tearing():
    tab = [[0, 1e3], [30, 2244e4], [80, 12381e4]]
    f = OpenSeesEngine._interp_base
    assert f(-5, tab) == 1e3                          # uplift -> tearing (C_MIN)
    assert f(100, tab) == 12381e4                     # flat beyond last point
    assert 2244e4 < f(55, tab) < 12381e4              # interpolates


def test_base_table_stored_on_model():
    tab = [[0, 1e3], [60, 8326e4]]
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, base_axial_table=tab))
    assert m.base_axial_table == tab


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
