"""Tests for the premium UI helpers (pure-HTML pieces, no Streamlit run)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import ui


def test_pill_variants():
    assert "pass" in ui.pill("PASS") and "PASS" in ui.pill("PASS")
    assert "fail" in ui.pill("FAIL")
    assert "idle" in ui.pill("not run")
    # html-safe
    assert "<span" in ui.pill("PASS")


def test_tile_html():
    h = ui.tile("Systems", 3)
    assert "rnr-tile" in h and "Systems" in h and "3" in h


def test_palettes_have_required_keys():
    keys = {"bg", "surface", "text", "muted", "border", "teal", "teal2",
            "grey", "shadow", "sidebar"}
    assert keys <= set(ui._LIGHT) and keys <= set(ui._DARK)
    # brand teal present in both palettes
    assert ui._LIGHT["teal"].startswith("#") and ui._DARK["teal"].startswith("#")


def test_dark_pref_roundtrip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert ui.load_dark_pref() is False        # no file -> default light
    ui._save_dark_pref(True)
    assert ui.load_dark_pref() is True
    ui._save_dark_pref(False)
    assert ui.load_dark_pref() is False


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
