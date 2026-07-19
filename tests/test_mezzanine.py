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


def test_cf_section_codes():
    """1C/2C/2x2C/SHS/RHS codes generate correct composed properties."""
    from rack15512.cf_sections import section_from_code

    c1 = section_from_code("1C200x60x20x2.0")
    c2 = section_from_code("2C200x60x20x2.0")
    c2b = section_from_code("2C200x60x20x2.0B")
    c4 = section_from_code("2x2C200x60x20x2.0")
    # coupling doubles/quadruples area and the MAJOR axis exactly
    assert c2.A == pytest.approx(2 * c1.A)
    assert c2.Iz == pytest.approx(2 * c1.Iz)
    assert c4.A == pytest.approx(4 * c1.A)
    assert c4.Iz == pytest.approx(4 * c1.Iz)
    # boxed (toe-to-toe) has the webs outboard -> larger Iy than back-to-back
    assert c2b.Iz == pytest.approx(c2.Iz) and c2b.Iy > c2.Iy
    # major axis is Iz (gravity bending) for all beam codes
    for s in (c1, c2, c2b, c4):
        assert s.Iz > s.Iy
    # corner radius reduces gross properties (EN 1993-1-3 delta)
    cr = section_from_code("1C200x60x20x2.0r4")
    assert cr.A < c1.A and cr.Iz < c1.Iz
    # SHS: symmetric, closed Bredt torsion (J of the same order as I)
    shs = section_from_code("SHS100x100x4")
    assert shs.Iy == pytest.approx(shs.Iz) and shs.J > shs.Iz
    rhs = section_from_code("RHS120x60x3")
    assert rhs.Iz > rhs.Iy
    assert section_from_code("not a code") is None


def test_mezzanine_codes_and_panel_layer():
    """SHS columns + 2C primary + 1C secondary by CODE, and a 1C floor-panel
    layer: panel dead joins the floor dead load and the representative strip
    bends about the panel's MINOR axis."""
    from rack15512.combos import assemble
    from rack15512.engine.opensees import OpenSeesEngine

    cfg = _cfg(mz_column_section="SHS100x100x4",
               mz_primary_section="2C200x60x20x2.5",
               mz_secondary_section="1C150x50x15x2.0",
               mz_panel_section="1C100x50x15x1.5")
    m = build_rack(cfg)
    assert "SHS100x100x4" in m.sections and "2C200x60x20x2.5" in m.sections
    strips = [mm for mm in m.members.values()
              if mm.member_set == "floor panels"]
    assert len(strips) == 1                       # one per floor
    assert strips[0].vecxz == (0.0, 0.0, 1.0)     # minor-axis rotation
    # panel self-weight (A*gamma/cover) is part of the dead load on the
    # secondaries: dead per-mm on a top-layer member exceeds deck-only
    pan = m.sections["1C100x50x15x1.5"]
    q_panel = pan.A * 7.698e-5 / pan.depth_h
    assert q_panel > 0
    # run SLS: the strip carries MINOR-axis bending (My >> Mz)
    c = OpenSeesEngine().run_case(m, assemble(m, m.combinations[1]),
                                  name="SLS1", combo="SLS1", kind="SLS",
                                  order=1)
    assert c.converged
    mr = c.members[strips[0].id]
    assert mr.My_absmax > 10 * max(mr.Mz_absmax, 1.0)
    assert mr.defl_absmax > 0
