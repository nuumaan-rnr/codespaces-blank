"""Tests for the EN 15512 check module and the full pipeline."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512 import io_json
from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks import buckling
from rack15512.checks.en15512 import all_ok, governing, run_checks
from rack15512.model import Imperfection


def test_buckling_curve_values():
    """Spot values of EN 1993-1-1 Table 6.2 (curve b)."""
    assert buckling.chi(0.2, "b") == pytest.approx(1.0)
    assert buckling.chi(1.0, "b") == pytest.approx(0.5970, abs=0.002)
    assert buckling.chi(1.5, "b") == pytest.approx(0.3422, abs=0.002)
    assert buckling.chi(0.5, "a") > buckling.chi(0.5, "d")


def test_imperfection_formula():
    imp = Imperfection(n_cols=4, phi_s=1 / 350.0, phi_l=0.0)
    # sqrt(0.5 + 1/4) * 2/350 = 0.004949
    assert imp.value() == pytest.approx(0.004949, abs=1e-5)
    assert Imperfection(phi=0.003).value() == 0.003
    # floor at phi_min
    assert Imperfection(n_cols=100, phi_s=1 / 5000.0).value() == 1 / 500.0
    with pytest.raises(ValueError):
        Imperfection().value()


def test_full_pipeline_and_json_roundtrip(tmp_path):
    model = build_rack(RackConfig(n_bays=2, level_heights=[1800.0, 1800.0]))
    # JSON round trip preserves the model
    p = tmp_path / "m.json"
    io_json.save(model, str(p))
    model2 = io_json.load(str(p))
    assert len(model2.members) == len(model.members)
    assert model2.members[1].hinge_i is None          # upright
    beams = [m for m in model2.members.values()
             if m.member_set == "pallet beams"]
    assert beams and beams[0].hinge_i.stiffness == 1.0e8

    cases = run_all(model2)
    assert all(c.converged for c in cases)
    # ULS combos run with both imperfection directions, SLS without
    uls = [c for c in cases if c.kind == "ULS"]
    sls = [c for c in cases if c.kind == "SLS"]
    assert all(c.imp_direction in (1, -1) for c in uls)
    assert all(c.imp_direction == 0 for c in sls)
    # second-order sway exceeds first-order sway under gravity + EHF
    swayed = [c for c in uls if c.sway_first_order]
    assert swayed and all(c.max_sway > c.sway_first_order for c in swayed)

    checks = run_checks(model2, cases)
    kinds = {c.check for c in checks}
    assert {"STRESS", "BUCKLING", "CONNECTOR", "DEFLECTION", "SWAY",
            "ALPHA_CR"} <= kinds
    gov = governing(checks)
    assert gov is not None and not gov.informative
    assert isinstance(all_ok(checks), bool)


def test_overloaded_rack_fails_checks():
    cfg = RackConfig(n_bays=2, level_heights=[2500.0] * 4,
                     pallet_load_per_level=60000.0)   # 6 t per bay per level
    model = build_rack(cfg)
    cases = run_all(model)
    checks = run_checks(model, cases)
    converged = [c for c in cases if c.kind == "ULS" and c.converged]
    # either the second-order analysis diverges (instability) or checks fail
    assert (not converged) or (not all_ok(checks))


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
