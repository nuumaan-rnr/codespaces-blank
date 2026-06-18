"""Upright continuous member-sets (RSTAB-style) and per-set buckling reporting."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.analysis import run_all
from rack15512.builder import RackConfig, build_rack
from rack15512.checks.en15512 import run_checks, upright_set_buckling_rows


def test_selective_upright_sets_are_storey_segments():
    m = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0],
                              depth=1000.0, frame_height=3600.0))
    up = [mm for mm in m.members.values() if mm.member_set == "uprights"]
    assert up and all(mm.set_label for mm in up)        # every upright tagged
    labels = {mm.set_label for mm in up}
    # the storey segments base->L1, L1->L2 and the top segment all appear
    assert any("base→L1" in lab for lab in labels)
    assert any("L1→L2" in lab for lab in labels)
    assert any("→top" in lab for lab in labels)
    # the set's down-aisle buckling length is the beam-to-beam segment
    seg = next(mm for mm in up if "L1→L2" in mm.set_label)
    assert abs(seg.L_buckling_z - 1500.0) < 1e-6


def test_upright_set_buckling_rows_aggregate_per_set():
    m = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0, 3000.0],
                              depth=1000.0, frame_height=3600.0))
    rows = upright_set_buckling_rows(m, run_checks(m, run_all(m)))
    assert rows
    assert all(r["Lcr_DA_mm"] > 0 and r["Lcr_CA_mm"] > 0 for r in rows)
    assert all(r["status"] in ("PASS", "FAIL") for r in rows)
    # the demand columns are present and numeric (N, My, Mz)
    assert all({"N_kN", "My_kNm", "Mz_kNm"} <= r.keys() for r in rows)
    assert all(r["util"] == max(r2["util"] for r2 in rows
                                if r2["set"] == r["set"]) for r in rows)
    # one row per distinct set; rows sorted worst-first
    assert len({r["set"] for r in rows}) == len(rows)
    assert rows == sorted(rows, key=lambda r: (-r["util"], r["set"]))


def test_drive_in_upright_sets_full_height():
    m = build_rack(RackConfig(
        system_type="drive_in", di_variant="drive_in", n_lanes=2, n_deep=3,
        lane_width=1440, pallet_depth=1000, deep_clearance=100, arm_length=200,
        beam_levels=[2400.0, 4900.0], frame_height=6000.0,
        mesh_beam=1, mesh_upright=1))
    up = [mm for mm in m.members.values()
          if mm.member_set in ("uprights", "end columns")]
    assert up
    assert all(mm.set_label and "base→top" in mm.set_label for mm in up)
    # one set per upright column (full height); not per storey
    rows = upright_set_buckling_rows(m, run_checks(m, run_all(m)))
    assert rows and all("base→top" in r["set"] for r in rows)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
