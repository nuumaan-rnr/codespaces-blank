"""Tests for the static (closed-form) upright pre-sizing helper."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import presize
from rack15512.analysis import run_all
from rack15512.builder import LevelSpec, RackConfig
from rack15512.checks.en15512 import run_checks
from rack15512.library import SectionLibrary
from rack15512.model import (Combination, LoadCase, NodalLoad, RackModel, Steel,
                             Support)


def test_upright_utilisation_matches_buckling_check():
    """The closed-form util must equal the analysis BUCKLING check for the same
    section, axial load and buckling length (pinned-pinned, K=1.0)."""
    lib = SectionLibrary.bundled()
    sec = lib.get(lib.names("upright")[0])
    L = 2000.0
    N = 55000.0                                   # N compression
    m = RackModel()
    m.materials["steel"] = Steel("steel", fy=355.0)
    sec.material = "steel"
    m.sections[sec.name] = sec
    m.add_node(1, 0.0, 0.0, 0.0)
    m.add_node(2, 0.0, 0.0, L)
    m.add_member(1, 1, 2, sec.name, mtype="beam", member_set="uprights")
    m.supports.append(Support(1, ux=True, uy=True, uz=True,
                              rx=True, ry=True, rz=True))
    lc = LoadCase("dead", "permanent")
    lc.nodal_loads.append(NodalLoad(2, fz=-N))
    m.load_cases["dead"] = lc
    m.combinations = [Combination("ULS1", "ULS", {"dead": 1.0},
                                  imperfection=False)]
    cases = run_all(m)
    checks = run_checks(m, cases)
    fea = next(c for c in checks if c.check == "BUCKLING")

    mr = cases[0].members[1]
    closed = presize.upright_utilisation(
        sec, m.materials["steel"], mr.length, mr.length, abs(mr.N_min))
    assert abs(closed["util_buckling"] - fea.utilization) < 1e-3


def test_suggest_ranks_and_recommends():
    lib = SectionLibrary.bundled()
    rows = presize.suggest_uprights(lib, lambda n: 355.0, N=60000.0,
                                    Lcr_y=1500.0, Lcr_z=1500.0)
    assert rows
    # sorted by area ascending
    assert [r["area"] for r in rows] == sorted(r["area"] for r in rows)
    # every passing row really is <= 1.0
    assert all(r["util"] <= 1.0 + 1e-9 for r in rows if r["passes"])
    # exactly one recommended, and it is the lightest passing section
    rec = [r for r in rows if r["recommended"]]
    assert len(rec) == 1
    lightest_pass = next(r for r in rows if r["passes"])
    assert rec[0]["name"] == lightest_pass["name"]


def test_static_demand_selective_and_drive_in():
    spr = presize.static_upright_demand(RackConfig(
        n_bays=3, levels=[LevelSpec(1500.0, "RHS 100x50x1.6", 20000.0),
                          LevelSpec(1500.0, "RHS 100x50x1.6", 20000.0)]))
    assert spr["N_design"] > 0 and spr["Lcr_y"] > 0 and spr["Lcr_z"] > 0

    di = presize.static_upright_demand(RackConfig(
        system_type="drive_in", di_variant="drive_in", n_lanes=3, n_deep=4,
        weight_per_pallet=10000.0, beam_levels=[1600.0, 3200.0, 4800.0],
        bracing_pitch=600.0))
    assert di["N_design"] > 0
    assert di["Lcr_z"] == 600.0                   # cross-aisle = bracing pitch
    assert di["n_levels"] == 3
