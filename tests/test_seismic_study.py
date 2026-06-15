"""Tests for the seismic bracing study (steel weight + auto-design)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.builder import RackConfig, build_rack
from rack15512.seismic_study import autodesign_seismic, steel_weight


def test_steel_weight_scales_with_size():
    small = steel_weight(build_rack(
        RackConfig(n_bays=1, beam_levels=[1500.0], depth=1000.0)))
    big = steel_weight(build_rack(
        RackConfig(n_bays=3, beam_levels=[1500.0, 3000.0], depth=1000.0)))
    assert small > 0 and big > small


def test_autodesign_seismic_returns_recommendation():
    cfg = RackConfig(n_bays=1, beam_levels=[1500.0], depth=1000.0)
    rec = autodesign_seismic(cfg, zone="II")
    assert set(rec) >= {"zone", "steps", "recommended", "passed", "config"}
    assert rec["zone"] == "II"
    assert rec["steps"] and "verdict" in rec["recommended"]
