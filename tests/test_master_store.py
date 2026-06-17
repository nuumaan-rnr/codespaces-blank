"""Tests for the in-app section-master store (CRUD)."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.master_store import MasterStore, StoredMaster
from rack15512.model import CrossSection

MASTER = os.path.join(os.path.dirname(__file__), "..", "examples",
                      "Master.xlsx")
needs_master = pytest.mark.skipif(not os.path.exists(MASTER),
                                  reason="examples/Master.xlsx not present")


@needs_master
def test_import_edit_delete_roundtrip(tmp_path):
    store = MasterStore(str(tmp_path / "masters"))
    m = store.import_xlsx(MASTER, name="Standard Master", company="Acme")
    assert m.id == "standard-master"
    assert m.company == "Acme" and "Acme" in store.companies()
    assert len(m.sections) == 50 and len(m.base_tables) == 25
    assert set(m.roles()) == {"upright", "beam", "bracing"}

    # reload from disk preserves everything (incl. a usable workbook)
    m = store.load(m.id)
    wb = m.to_workbook()
    assert wb.library.get("UP0016").A == pytest.approx(390.0)
    k, _ = wb.base_stiffness("UP0016", 40e3)
    assert k > 0

    # edit a field
    m.update_fields("UP0016", fy=355.0, A=500.0)
    store.save(m)
    m = store.load(m.id)
    assert m.fy["UP0016"] == 355.0
    assert m.sections["UP0016"]["A"] == 500.0
    assert m.to_workbook().library.get("UP0016").A == 500.0

    # delete a section (and its base table)
    assert "UP0026" in m.sections
    m.delete_section("UP0026")
    store.save(m)
    m = store.load(m.id)
    assert "UP0026" not in m.sections
    assert "UP0026" not in m.base_tables
    assert len(m.sections) == 49

    # delete the whole master
    store.delete(m.id)
    assert not store.exists(m.id)
    assert store.list() == []


def test_create_and_add_section(tmp_path):
    store = MasterStore(str(tmp_path / "masters"))
    m = store.create("Custom", description="hand built")
    m.upsert_section(CrossSection(
        name="UP-NEW", material="steel", role="upright",
        A=700.0, Iy=8.0e5, Iz=1.2e6, J=1200.0, Wely=1.6e4, Welz=2.4e4,
        depth_h=120.0, width_b=63.0, t=2.0), fy=350.0)
    m.set_base_table("UP-NEW", [(30e3, 4.0e7, 2.0e6), (50e3, 7.0e7, 3.0e6)])
    store.save(m)

    m = store.load(m.id)
    assert m.names("upright") == ["UP-NEW"]
    assert m.fy["UP-NEW"] == 350.0
    wb = m.to_workbook()
    sec = wb.library.get("UP-NEW")
    assert sec.depth_h == 120.0 and sec.A == 700.0
    k, mrd = wb.base_stiffness("UP-NEW", 40e3)      # midpoint interpolation
    assert k == pytest.approx(5.5e7) and mrd == pytest.approx(2.5e6)


def test_unique_ids(tmp_path):
    store = MasterStore(str(tmp_path / "masters"))
    a = store.create("Master")
    b = store.create("Master")
    assert a.id == "master" and b.id == "master-2"


def test_stored_master_builds_a_rack(tmp_path):
    """A stored master drives build_rack exactly like the .xlsx did."""
    if not os.path.exists(MASTER):
        pytest.skip("master not present")
    from rack15512.builder import RackConfig, build_rack
    store = MasterStore(str(tmp_path / "masters"))
    m = store.import_xlsx(MASTER, name="M", company="Acme")
    model = build_rack(RackConfig(
        n_bays=1, beam_levels=[1500.0, 3000.0],
        master=store.load(m.id).to_workbook(),
        upright_section="UP0016", beam_section="RHS 112x50x2.0",
        brace_section="C 36X21X1.5", base_stiffness="auto"))
    assert model.validate() == []
    assert model.base_plate.m_rd_n is not None       # base table carried over


def test_builtin_others_master(tmp_path):
    """ensure_builtin() seeds the 'others' master with the Drivein Rail section
    and the drive in connector (with its connector stiffness)."""
    store = MasterStore(str(tmp_path / "masters"))
    store.ensure_builtin()
    assert store.exists("others")
    m = store.load("others")
    assert m.name == "others"
    assert "Drivein Rail" in m.sections
    assert "drive in connector" in m.sections
    lib = m.library
    rail = lib.get("Drivein Rail")
    assert rail.A == 709.8 and rail.Iy == 1.8056e6      # RSTAB rail props
    conn = lib.get("drive in connector")
    assert conn.connector_k == 1.0e6                    # RSTAB Konsole hinge
    # idempotent: a second call does not duplicate
    store.ensure_builtin()
    assert sum(1 for x in store.list() if x.id == "others") == 1


def test_company_is_mandatory_for_import(tmp_path):
    if not os.path.exists(MASTER):
        pytest.skip("master not present")
    store = MasterStore(str(tmp_path / "masters"))
    with pytest.raises(ValueError):
        store.import_xlsx(MASTER, name="NoCo")          # no company -> rejected
    assert store.list() == []                           # nothing stored


def test_company_registry_and_grouping(tmp_path):
    store = MasterStore(str(tmp_path / "masters"))
    store.add_company("Alpha")
    store.add_company("Beta")
    assert store.companies() == ["Alpha", "Beta"]
    if os.path.exists(MASTER):
        store.import_xlsx(MASTER, name="A-master", company="Alpha")
        grouped = store.by_company()
        assert "Alpha" in grouped and grouped["Alpha"][0].company == "Alpha"
    store.delete_company("Beta")
    assert "Beta" not in store.companies()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
