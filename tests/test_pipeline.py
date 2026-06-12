"""End-to-end pipeline tests on the example rack (3D, internal engine)."""

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
    n_cols = geo.n_frames * 2                       # front + rear uprights
    # two beams (front/rear faces) per bay per level
    assert len(model.member_sets["beams"]) == 2 * geo.n_bays * geo.n_levels
    # one support per upright base
    assert len(model.supports) == n_cols
    # bracing: one strut + one diagonal per panel per frame
    n_panels = len({round(m.level) for m in model.braces}) if model.braces else 0
    assert len(model.member_sets["braces"]) == 2 * n_panels * geo.n_frames
    # uprights are split at every beam/brace node
    seg_per_col = len(model.member_sets["uprights"]) / n_cols
    assert seg_per_col == int(seg_per_col) and seg_per_col >= geo.n_levels
    # all beams have semi-rigid connectors at both ends
    for b in model.beams:
        assert b.hinge_i.my == cfg.connections.beam_end_stiffness
        assert b.hinge_j.my == cfg.connections.beam_end_stiffness
    # 3D coordinates: both faces present
    ys = {round(n.y, 6) for n in model.nodes.values()}
    assert ys == {0.0, geo.depth}


def test_load_cases_and_imperfections(cfg):
    model = build_rack_model(cfg)
    lcs = build_load_cases(cfg, model)
    assert set(lcs) == {"DL", "UL", "PLX", "PLY", "IMPX", "IMPY"}
    assert len(lcs["UL"].line_loads) == len(model.beams)
    # imperfection forces are proportional to phi * V, per direction
    per_beam = cfg.loads.unit_load_per_beam + (
        cfg.loads.beam_dead_load + cfg.beam_section.self_weight * 9.81
    ) * cfg.geometry.bay_width
    total_v = per_beam * cfg.geometry.n_bays * 2 * cfg.geometry.n_levels
    total_hx = sum(p.fx for p in lcs["IMPX"].point_loads)
    total_hy = sum(p.fy for p in lcs["IMPY"].point_loads)
    assert total_hx == pytest.approx(cfg.sway_imperfection_x() * total_v, rel=1e-9)
    assert total_hy == pytest.approx(cfg.sway_imperfection_y() * total_v, rel=1e-9)
    assert all(p.fy == 0.0 for p in lcs["IMPX"].point_loads)
    assert all(p.fx == 0.0 for p in lcs["IMPY"].point_loads)


def test_default_combinations(cfg):
    combos = {c.id: c for c in build_default_combinations(cfg)}
    assert set(combos) == {"ULS_DA1", "ULS_DA2", "ULS_CA",
                           "SLS", "SLS_SWX", "SLS_SWY"}
    assert combos["ULS_DA1"].second_order
    assert combos["ULS_DA1"].factors == {"DL": 1.3, "UL": 1.4, "IMPX": 1.4}
    assert combos["ULS_CA"].factors == {"DL": 1.3, "UL": 1.4,
                                        "IMPY": 1.4, "PLY": 1.4}
    assert not combos["SLS"].second_order
    assert combos["SLS_SWY"].factors == {"DL": 1.0, "UL": 1.0,
                                         "IMPY": 1.0, "PLY": 1.0}


def test_analysis_equilibrium_and_sway(output):
    res = output.results
    assert set(res.combos) == {"ULS_DA1", "ULS_DA2", "ULS_CA",
                               "SLS", "SLS_SWX", "SLS_SWY"}
    for cid in ("ULS_DA1", "ULS_DA2", "ULS_CA"):
        cr = res.combos[cid]
        assert cr.converged and cr.second_order and cr.iterations >= 2
    # gravity equilibrium at ULS_DA1: sum Fz reactions == factored loads
    cr = res.combos["ULS_DA1"]
    total_react = sum(r.fz for r in cr.reactions.values())
    g = 9.81
    cfg, model = output.cfg, output.model
    dead = sum(m.section.self_weight * g * model.member_length(m.id)
               for m in model.members.values())
    dead += sum(cfg.loads.beam_dead_load * model.member_length(m.id)
                for m in model.beams)
    unit = cfg.loads.unit_load_per_beam * len(model.beams)
    expected = 1.3 * dead + 1.4 * unit
    assert total_react == pytest.approx(expected, rel=1e-6)
    # rack sways down-aisle (+X) in the DA combo, cross-aisle (+Y) in CA
    top = max(output.model.top_nodes)
    assert cr.nodes[top].ux > 0.0
    assert res.combos["ULS_CA"].nodes[top].uy > 0.0


def test_biaxial_moments_present(output):
    """The 3D model produces moments about BOTH axes of the uprights:
    My from the down-aisle combo, Mz from the cross-aisle combo."""
    res = output.results
    my_da = max(res.combos["ULS_DA1"].members[m.id].My_abs_max
                for m in output.model.uprights)
    mz_ca = max(res.combos["ULS_CA"].members[m.id].Mz_abs_max
                for m in output.model.uprights)
    assert my_da > 10.0     # Nm, down-aisle frame action
    assert mz_ca > 1.0      # Nm, cross-aisle bending exists (braced, smaller)
    # braces actually carry the cross-aisle load
    n_brace = max(abs(res.combos["ULS_CA"].members[m.id].N1)
                  for m in output.model.braces)
    assert n_brace > 100.0


def test_second_order_amplifies_sway(output, cfg):
    import copy
    cfg1 = copy.deepcopy(cfg)
    cfg1.analysis.second_order = False
    out1 = run(cfg1)
    top = max(output.model.top_nodes)
    u2 = output.results.combos["ULS_DA1"].nodes[top].ux
    u1 = out1.results.combos["ULS_DA1"].nodes[top].ux
    assert u2 > u1 > 0.0


def test_checks_and_report(output):
    rep = output.report
    kinds = {r.check for r in rep.results}
    assert {"cross_section", "buckling", "brace", "connector",
            "deflection", "sway"} <= kinds
    # buckling notes mention both axes
    buck = [r for r in rep.results if r.check == "buckling"]
    assert buck and all("chi_y" in r.note and "chi_z" in r.note for r in buck)
    # sway is checked in both directions on the SLS sway combos
    sway = [r for r in rep.results if r.check == "sway"]
    assert {r.combo for r in sway} == {"SLS_SWX", "SLS_SWY"}
    assert any(r.ratio > 0.0 for r in sway)

    md = to_markdown(output.cfg, output.model, output.results, rep)
    assert "EN 15512" in md and "Verdict" in md and "biaxial" in md
    js = to_json(output.cfg, output.model, output.results, rep)
    assert '"all_passed"' in js


def test_example_rack_passes(output):
    """The shipped example should be a passing design."""
    assert output.report.all_passed, [
        (r.check, r.target, round(r.ratio, 2))
        for r in output.report.results if not r.passed
    ]


def test_no_bracing_variant_still_solves(cfg):
    """pattern: none -> cross-aisle stability from base fixity alone."""
    import copy
    c = copy.deepcopy(cfg)
    c.geometry.bracing.pattern = "none"
    out = run(c)
    cr = out.results.combos["ULS_CA"]
    assert cr.converged
    # at the frame that carries the placement load, the top sways +Y;
    # without bracing the cross-aisle response is much softer than braced
    top_lvl = len(out.model.level_elevations) - 1
    loaded_top = out.model.grid[(0, 0, top_lvl)]
    assert cr.nodes[loaded_top].uy > 0.0
