"""End-to-end pipeline tests on the example rack with the internal engine."""

import os

import pytest

from rackapp.config import RackConfig
from rackapp.loads import build_default_combinations, build_load_cases
from rackapp.model import build_rack_model
from rackapp.pipeline import run
from rackapp.report import to_json, to_markdown

EXAMPLE = os.path.join(os.path.dirname(__file__), "..", "examples",
                       "rack_example.yaml")


@pytest.fixture(scope="module")
def cfg():
    c = RackConfig.from_yaml(EXAMPLE)
    c.analysis.engine = "internal"
    return c


@pytest.fixture(scope="module")
def output(cfg):
    return run(cfg)


def test_geometry_counts(cfg):
    model = build_rack_model(cfg)
    geo = cfg.geometry
    n_up = geo.n_uprights
    assert len(model.nodes) == n_up * (geo.n_levels + 1)
    assert len(model.member_sets["uprights"]) == n_up * geo.n_levels
    assert len(model.member_sets["beams"]) == geo.n_bays * geo.n_levels
    assert len(model.supports) == n_up
    # all beams have semi-rigid connectors at both ends
    for b in model.beams:
        assert b.hinge_i.stiffness == cfg.connections.beam_end_stiffness
        assert b.hinge_j.stiffness == cfg.connections.beam_end_stiffness


def test_load_cases_and_imperfection(cfg):
    model = build_rack_model(cfg)
    lcs = build_load_cases(cfg, model)
    assert set(lcs) == {"DL", "UL", "PL", "IMP"}
    # unit loads on every beam
    assert len(lcs["UL"].line_loads) == len(model.beams)
    # imperfection forces are horizontal and proportional to phi * V
    phi = cfg.sway_imperfection()
    total_h = sum(p.fx for p in lcs["IMP"].point_loads)
    per_beam = cfg.loads.unit_load_per_beam + (
        cfg.loads.beam_dead_load + cfg.beam_section.self_weight * 9.81
    ) * cfg.geometry.bay_width
    total_v = per_beam * cfg.geometry.n_bays * cfg.geometry.n_levels
    assert total_h == pytest.approx(phi * total_v, rel=1e-9)


def test_default_combinations(cfg):
    combos = build_default_combinations(cfg)
    ids = [c.id for c in combos]
    assert ids == ["ULS1", "ULS2", "SLS"]
    uls1 = combos[0]
    assert uls1.second_order
    assert uls1.factors == {"DL": 1.3, "UL": 1.4, "IMP": 1.4}
    sls = combos[2]
    assert not sls.second_order
    assert sls.factors == {"DL": 1.0, "UL": 1.0}


def test_analysis_results(output):
    res = output.results
    assert set(res.combos) == {"ULS1", "ULS2", "SLS"}
    for cid in ("ULS1", "ULS2"):
        cr = res.combos[cid]
        assert cr.converged and cr.second_order and cr.iterations >= 2
    # gravity equilibrium at ULS1: sum Fz reactions == factored vertical load
    cr = res.combos["ULS1"]
    total_react = sum(r.fz for r in cr.reactions.values())
    g = 9.81
    geo = output.cfg.geometry
    upright_w = sum(output.cfg.upright_section.self_weight * g *
                    output.model.member_length(m.id)
                    for m in output.model.uprights)
    beam_w = sum((output.cfg.beam_section.self_weight * g +
                  output.cfg.loads.beam_dead_load) *
                 output.model.member_length(m.id)
                 for m in output.model.beams)
    unit = output.cfg.loads.unit_load_per_beam * geo.n_bays * geo.n_levels
    expected = 1.3 * (upright_w + beam_w) + 1.4 * unit
    assert total_react == pytest.approx(expected, rel=1e-6)
    # rack sways in +X under imperfection forces
    top = max(output.model.top_nodes)
    assert cr.nodes[top].ux > 0.0


def test_second_order_amplifies_sway(output, cfg):
    """The 2nd-order sway must exceed the 1st-order sway."""
    import copy
    cfg1 = copy.deepcopy(cfg)
    cfg1.analysis.second_order = False
    out1 = run(cfg1)
    top = max(output.model.top_nodes)
    u2 = output.results.combos["ULS1"].nodes[top].ux
    u1 = out1.results.combos["ULS1"].nodes[top].ux
    assert u2 > u1 > 0.0


def test_checks_and_report(output):
    rep = output.report
    kinds = {r.check for r in rep.results}
    assert {"cross_section", "buckling", "connector", "deflection", "sway"} <= kinds
    gov = rep.governing()
    assert gov is not None and gov.ratio > 0.0

    md = to_markdown(output.cfg, output.model, output.results, rep)
    assert "EN 15512" in md and "Verdict" in md
    js = to_json(output.cfg, output.model, output.results, rep)
    assert '"all_passed"' in js


def test_example_rack_passes(output):
    """The shipped example should be a passing design."""
    assert output.report.all_passed, [
        (r.check, r.target, round(r.ratio, 2))
        for r in output.report.results if not r.passed
    ]
