"""Structural-mezzanine builder tests (system_type "mezzanine")."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from collections import Counter

import pytest

from rack15512.builder import RackConfig, build_rack
from rack15512.mezzanine import FLOOR_TYPES


def _cfg(**kw):
    base = dict(system_type="mezzanine", name="MZ", mz_bays_x=2, mz_bays_y=1,
                mz_bay_x=4000.0, mz_bay_y=3000.0, mz_n_floors=1,
                mz_floor_height=3000.0, mz_secondary_spacing=1000.0,
                mz_live_load=3.0)
    base.update(kw)
    return RackConfig(**base)


def test_mezzanine_grid_and_sets():
    m = build_rack(_cfg())
    sets = Counter(mm.member_set for mm in m.members.values())
    # (bays_x+1)*(bays_y+1) columns x 1 storey
    assert sets["columns"] == 3 * 2
    assert sets["primary beams"] > 0 and sets["secondary beams"] > 0
    assert sets["bracing"] > 0                       # braced by default
    assert "joists" not in sets                      # no joist layer
    assert len(m.supports) == 6                      # one per column base
    assert m.supports[0].ux is True and m.supports[0].rx is False  # pinned
    # buckling targets the columns; per-storey buckling lengths set
    assert m.checks.buckling_sets == ["columns"]
    colm = next(mm for mm in m.members.values() if mm.member_set == "columns")
    assert colm.L_buckling_y == 3000.0 and colm.L_torsion == 3000.0
    assert colm.set_label.startswith("Column")
    # ULS + SLS combinations with the config factors
    assert [c.kind for c in m.combinations] == ["ULS", "SLS"]
    assert m.combinations[0].factors == {"dead": 1.3, "live": 1.4}


def test_mezzanine_floor_load_totals():
    cfg = _cfg()
    m = build_rack(cfg)
    area = (cfg.mz_bays_x * cfg.mz_bay_x) * (cfg.mz_bays_y * cfg.mz_bay_y)
    tot = sum(abs(ml.qz) * m.member_length(m.members[ml.member])
              for ml in m.load_cases["live"].member_loads)
    assert tot == pytest.approx(cfg.mz_live_load * 1e-3 * area, rel=1e-6)
    # flooring dead on the same layer + self-weight on every member
    q_deck = FLOOR_TYPES[cfg.mz_floor_type] * 1e-3 * area
    dead_tot = sum(abs(ml.qz) * m.member_length(m.members[ml.member])
                   for ml in m.load_cases["dead"].member_loads)
    assert dead_tot > q_deck                        # deck + self-weight


def test_mezzanine_joist_layer_carries_the_floor():
    cfg = _cfg(mz_joist_section="BM-100x40x1.5", mz_joist_spacing=500.0)
    m = build_rack(cfg)
    sets = Counter(mm.member_set for mm in m.members.values())
    assert sets["joists"] > 0
    # live load rests on the joists only, and still totals q * area
    live_mids = {ml.member for ml in m.load_cases["live"].member_loads}
    assert all(m.members[i].member_set == "joists" for i in live_mids)
    area = (cfg.mz_bays_x * cfg.mz_bay_x) * (cfg.mz_bays_y * cfg.mz_bay_y)
    tot = sum(abs(ml.qz) * m.member_length(m.members[ml.member])
              for ml in m.load_cases["live"].member_loads)
    assert tot == pytest.approx(cfg.mz_live_load * 1e-3 * area, rel=1e-6)


def test_mezzanine_connection_and_stability_options():
    # pinned primary connections in a braced frame
    m = build_rack(_cfg(mz_primary_conn="pinned"))
    pb = [mm for mm in m.members.values() if mm.member_set == "primary beams"
          and mm.hinge_i is not None]
    assert pb and pb[0].hinge_i.rz == 0.0
    # bracing off -> moment frame: pinned request is overridden, no braces
    m2 = build_rack(_cfg(mz_bracing=False, mz_primary_conn="pinned"))
    assert not any(mm.member_set == "bracing" for mm in m2.members.values())
    assert all(mm.hinge_i is None and mm.hinge_j is None
               for mm in m2.members.values()
               if mm.member_set == "primary beams")
    # fixed bases
    m3 = build_rack(_cfg(mz_base_fixed=True))
    assert m3.supports[0].rx is True and m3.supports[0].ry is True


def test_mezzanine_runs_and_checks():
    from rack15512.checks.en15512 import run_checks
    from rack15512.combos import apply_ehf, assemble
    from rack15512.engine.opensees import OpenSeesEngine
    from rack15512.model import DIRECTION_VECTORS

    cfg = _cfg(mz_live_load=1.0)
    m = build_rack(cfg)
    uls = m.combinations[0]
    loads = apply_ehf(m, assemble(m, uls), m.imperfection.value_for("+x"),
                      DIRECTION_VECTORS["+x"])
    case = OpenSeesEngine().run_case(m, loads, name="ULS1", combo="ULS1",
                                     kind="ULS", order=1, imp_direction="+x")
    assert case.converged
    cols = [mr.N_min for mid, mr in case.members.items()
            if m.members[mid].member_set == "columns"]
    assert min(cols) < 0                            # columns in compression
    sls = OpenSeesEngine().run_case(
        m, assemble(m, m.combinations[1]), name="SLS1", combo="SLS1",
        kind="SLS", order=1)
    assert sls.converged
    checks = run_checks(m, [case, sls])
    kinds = {c.check for c in checks}
    assert "BUCKLING" in kinds and "DEFLECTION" in kinds
    # buckling only on the columns (checks.buckling_sets)
    for c in checks:
        if c.check == "BUCKLING" and c.target.startswith("member"):
            mid = int(c.target.split()[1])
            assert m.members[mid].member_set == "columns"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
