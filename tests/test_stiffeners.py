"""Bolted upright stiffeners modelled as parallel members sharing the upright
end nodes (composite via shared nodes)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks, upright_set_buckling_rows

_BASE = dict(n_bays=1, beam_levels=[1500.0, 3000.0], depth=1000.0,
             frame_height=3600.0)
_RH = 1500.0
_STIFF = "UP-100x100x2.0"          # a valid upright-role section name


def _build(**extra):
    return build_rack(RackConfig(**_BASE, **extra))


def test_stiffener_disabled_by_default():
    m = _build()
    assert not any(mm.member_set == "upright stiffeners"
                   for mm in m.members.values())
    assert m.checks.buckling_sets == ["uprights"]


def test_stiffeners_added_only_in_lower_zone():
    m = _build(stiffener_section=_STIFF, reinforce_height=_RH)
    stiff = [mm for mm in m.members.values()
             if mm.member_set == "upright stiffeners"]
    assert stiff
    # each stiffener shares its (node_i, node_j) with exactly one upright member
    up_pairs = {(mm.node_i, mm.node_j) for mm in m.members.values()
                if mm.member_set == "uprights"}
    for s in stiff:
        assert (s.node_i, s.node_j) in up_pairs
        ztop = max(m.nodes[s.node_i].z, m.nodes[s.node_j].z)
        assert ztop <= _RH + 1e-6
    # count == number of upright segments whose top is within the zone
    expect = sum(1 for mm in m.members.values()
                 if mm.member_set == "uprights"
                 and max(m.nodes[mm.node_i].z, m.nodes[mm.node_j].z) <= _RH + 1e-6)
    assert len(stiff) == expect
    # buckling_sets now includes the stiffeners
    assert "upright stiffeners" in m.checks.buckling_sets


def test_node_exists_at_reinforce_height():
    m = _build(stiffener_section=_STIFF, reinforce_height=1200.0)
    assert any(abs(nd.z - 1200.0) < 1e-6 for nd in m.nodes.values())


def test_stiffeners_buckling_checked_and_grouped():
    m = _build(stiffener_section=_STIFF, reinforce_height=_RH)
    checks = run_checks(m, run_all(m))
    bb = [c for c in checks if c.check == "BUCKLING"
          and c.member_set == "upright stiffeners"]
    assert bb                                   # stiffeners are buckling-checked
    rows = upright_set_buckling_rows(m, checks)
    # stiffeners share the upright set_label -> no duplicate set rows
    assert len({r["set"] for r in rows}) == len(rows)


def test_solver_converges_with_parallel_stiffeners():
    # the coincident-node risk: two collinear beams on the same node pair, meshed
    for mesh in (1, 2):
        m = _build(stiffener_section=_STIFF, reinforce_height=_RH,
                   mesh_upright=mesh)
        cases = run_all(m)
        assert cases
        stiff_ids = [mid for mid, mm in m.members.items()
                     if mm.member_set == "upright stiffeners"]
        # the stiffeners carry force (solver handled the parallel members)
        seen = any(sid in c.members for c in cases for sid in stiff_ids)
        assert seen


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
