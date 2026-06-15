"""Tests for the standard 1C lipped-channel section generator."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512.cf_sections import STD_1C, parse_1c, standard_1c_sections


def test_std_1c_family():
    assert len(STD_1C) >= 6
    assert all(n.startswith("1C") for n in STD_1C)
    assert any("60x40" in n for n in STD_1C)
    assert any("80x40" in n for n in STD_1C)


def test_parse_1c():
    assert parse_1c("1C60x40x10x1.6") == (60.0, 40.0, 10.0, 1.6)
    assert parse_1c("not-a-section") is None


def test_standard_sections_valid():
    secs = standard_1c_sections()
    assert set(secs) == set(STD_1C)
    for name, s in secs.items():
        assert s.A > 0 and s.Iy > 0 and s.Iz > 0 and s.J > 0
        assert s.Wely > 0 and s.Welz > 0
        assert s.role == "bracing"
        assert s.t and s.depth_h and s.width_b
