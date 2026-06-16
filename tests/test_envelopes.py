"""Tests for envelopes, the ignore-load switches, row-spacer beams and the
interactive viewer."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.analysis import run_all
from rack15512.builder import LevelSpec, RackConfig, build_rack
from rack15512.checks.en15512 import run_checks
from rack15512.envelopes import build_envelopes


def _model(**kw):
    base = dict(n_bays=1,
                levels=[LevelSpec(1500.0, "BM-110x50x1.5", 18000.0)])
    base.update(kw)
    return build_rack(RackConfig(**base))


def test_ignore_placement_and_accidental():
    full = _model()
    assert "placement" in full.load_cases
    assert "accidental_x" in full.load_cases
    assert any("acc" in c.name for c in full.combinations)

    none = _model(include_placement=False, include_accidental=False)
    assert "placement" not in none.load_cases
    assert "accidental_x" not in none.load_cases
    # only the gravity ULS/SLS pair remains
    assert [c.name for c in none.combinations] == ["ULS1", "SLS1"]
    assert set(none.load_cases) == {"dead", "pallets"}


def test_build_envelopes_tolerates_stale_results():
    """Results from a heavier model (more members) must not crash envelope
    building against a lighter, edited model (KeyError guard)."""
    big = build_rack(RackConfig(module="back-to-back", n_bays=1, depth=1000.0,
                                b2b_gap=250.0, beam_levels=[1500.0],
                                spine_bracing=True, plan_bracing=True))
    big.combinations = big.combinations[:1]
    big.imperfection.directions = ["+x"]
    cases = run_all(big)
    checks = run_checks(big, cases)
    small = build_rack(RackConfig(module="back-to-back", n_bays=1,
                                  depth=1000.0, b2b_gap=250.0,
                                  beam_levels=[1500.0]))
    assert len(small.members) < len(big.members)
    envs = build_envelopes(small, cases, checks)        # must not raise
    uls = next(e for e in envs if e.name == "ULS (all)")
    assert set(uls.members) <= set(small.members)

    # rendering the interactive figure against the mismatched geometry must
    # also not raise (stale case lacks displacements for some current nodes)
    from rack15512.iviewer import figure_for_case, figure_for_envelope
    figure_for_envelope(small, uls, scale=30)
    figure_for_case(small, cases[0], checks, scale=30)


def test_frame_spacer_is_beam_and_bracing_is_truss():
    m = _model(module="back-to-back", depth=1000.0, b2b_gap=250.0)
    spacers = [x for x in m.members.values()
               if x.member_set == "frame spacer"]
    braces = [x for x in m.members.values() if x.member_set == "bracing"]
    # frame spacers are beam elements (they tie the racks/spine in-plane);
    # the diagonal bracing stays truss (pinned)
    assert spacers and all(s.mtype == "beam" for s in spacers)
    assert braces and all(b.mtype == "truss" for b in braces)
    assert all(s.area_factor == 1.0 for s in spacers)
    assert all(b.area_factor == pytest.approx(0.15) for b in braces)


def test_envelopes_group_uls_sls():
    m = _model(module="back-to-back", depth=1000.0,
               levels=[LevelSpec(1500.0, "BM-110x50x1.5", 18000.0),
                       LevelSpec(1500.0, "BM-110x50x1.5", 18000.0)])
    cases = run_all(m)
    checks = run_checks(m, cases)
    envs = build_envelopes(m, cases, checks)
    names = [e.name for e in envs]
    assert "ULS (all)" in names and "SLS (all)" in names
    uls = next(e for e in envs if e.name == "ULS (all)")
    sls = next(e for e in envs if e.name == "SLS (all)")
    assert all(c.kind == "ULS" for c in uls.cases)
    assert all(c.kind == "SLS" for c in sls.cases)
    # enveloped member extremes cover every member
    assert set(uls.members) == set(m.members)
    # the ULS envelope's most-compressed upright is at least as severe as
    # any single ULS case's
    a_member = next(mid for mid, e in uls.members.items()
                    if e.member_set == "uprights")
    case_mins = [c.members[a_member].N_min for c in uls.cases]
    assert uls.members[a_member].N_min == pytest.approx(min(case_mins))
    # reactions enveloped per node
    assert uls.reactions
    assert uls.governing is not None
    # real per-member EN 15512 utilisation is carried for colouring
    assert uls.member_util
    # member_util colours members, so it equals the worst MEMBER-level check;
    # the overall governing may be a node check (anchorage/base) and is at
    # least as severe as the worst member utilisation
    uls_names = {c.name for c in uls.cases}
    worst_member = max(c.utilization for c in checks
                       if c.case in uls_names and not c.informative
                       and c.target.startswith("member"))
    assert max(uls.member_util.values()) == pytest.approx(worst_member,
                                                          rel=1e-6)
    assert uls.governing.utilization >= max(uls.member_util.values()) - 1e-9


def test_interactive_figures_build():
    m = _model()
    cases = run_all(m)
    checks = run_checks(m, cases)
    envs = build_envelopes(m, cases, checks)
    from rack15512.iviewer import figure_for_case, figure_for_envelope
    f1 = figure_for_case(m, cases[0], checks, scale=25)
    f2 = figure_for_envelope(m, envs[0], scale=25)
    # per-member hover markers carry utilisation + forces; supports carry reactions
    markers1 = next(t for t in f1.data if t.name == "members")
    assert any("utilisation" in t and "kN" in t for t in markers1.text)
    sup1 = next(t for t in f1.data if t.name == "supports")
    assert any("reactions" in t for t in sup1.text)
    # members coloured by DISCRETE utilisation band (green/orange/red), one
    # colour per member, no continuous colour bar
    markers2 = next(t for t in f2.data if t.name == "members")
    assert len(markers2.marker.color) == len(m.members)
    assert set(markers2.marker.color) <= {"#2ca02c", "#ff7f0e", "#d62728"}
    # the band line traces double as the colour key (legend)
    band_names = {"util < 0.9", "util 0.9–1.0", "util > 1.0 (fail)"}
    assert any(t.name in band_names for t in f2.data)


def test_beam_moment_and_load_direction():
    """Gravity loads act downward toward the supports: midspan beam moment
    is sagging (+Mz), midspan deflects down, base reaction is upward."""
    m = _model()
    cases = run_all(m)
    sls = next(c for c in cases if c.kind == "SLS")
    beam = next(mid for mid, x in m.members.items()
                if x.member_set == "pallet beams")
    mr = sls.members[beam]
    mid = min(mr.stations, key=lambda s: abs(s.x - mr.length / 2))
    assert mid.Mz > 0                      # sagging positive
    assert mid.defl_y < 0                  # deflects downward
    # every support carries upward vertical reaction, summing to the load
    rz = [r[2] for r in sls.reactions.values()]
    assert all(v >= -1.0 for v in rz)      # no spurious downward pull
    assert sum(rz) > 0


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
