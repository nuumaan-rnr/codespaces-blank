"""Tests for JSON model serialisation (io_json)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import io_json
from rack15512.builder import RackConfig, build_rack


def test_model_dict_round_trip():
    m = build_rack(RackConfig(n_bays=2, beam_levels=[2000.0, 4000.0],
                              depth=1000.0))
    m2 = io_json.model_from_dict(io_json.model_to_dict(m))
    assert len(m2.nodes) == len(m.nodes)
    assert len(m2.members) == len(m.members)
    assert set(m2.sections) == set(m.sections)
    assert len(m2.supports) == len(m.supports)
    assert set(m2.load_cases) == set(m.load_cases)
    assert len(m2.combinations) == len(m.combinations)


def test_save_load(tmp_path):
    m = build_rack(RackConfig(n_bays=1, beam_levels=[1500.0], depth=1000.0))
    p = tmp_path / "model.json"
    io_json.save(m, str(p))
    assert p.exists() and p.stat().st_size > 0
    m2 = io_json.load(str(p))
    assert len(m2.members) == len(m.members)
    assert set(m2.sections) == set(m.sections)
