"""Tests for the project / system / configuration store."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from rack15512.builder import LevelSpec, RackConfig
from rack15512.project import (ProjectStore, rackconfig_from_dict,
                               rackconfig_to_dict)


def test_rackconfig_roundtrip():
    cfg = RackConfig(
        name="cfg", module="back-to-back", n_bays=4, bracing_type="X",
        levels=[LevelSpec(gap=1500.0, beam_section="B1", pallet_load=18000.0),
                LevelSpec(gap=1700.0, beam_section="B2", pallet_load=22000.0)],
        bolt_d=12.0, plate_t=4.0)
    d = rackconfig_to_dict(cfg)
    assert "library" not in d and "master" not in d   # not serialised
    cfg2 = rackconfig_from_dict(d)
    assert cfg2.module == "back-to-back" and cfg2.n_bays == 4
    assert cfg2.bracing_type == "X"
    assert len(cfg2.levels) == 2
    assert cfg2.levels[0].beam_section == "B1"
    assert cfg2.levels[1].pallet_load == 22000.0
    # forward-compatible: unknown keys are ignored
    d["some_future_field"] = 99
    assert rackconfig_from_dict(d).n_bays == 4


def test_project_system_configuration_hierarchy(tmp_path):
    store = ProjectStore(str(tmp_path / "projects"))
    proj = store.create_project("Test Job", client="ACME",
                                engineer="R. Nair")
    assert proj.id == "test-job"
    assert store.exists(proj.id)

    # a system with two configurations
    sysm = store.add_system(proj.id, "Aisle 1")
    c1 = store.add_configuration(proj.id, sysm.id, "Base case",
                                 RackConfig(n_bays=3), notes="initial")
    c2 = store.add_configuration(proj.id, sysm.id, "Heavier upright",
                                 RackConfig(n_bays=3, upright_section="UPX"))
    # a second system under the same project
    sys2 = store.add_system(proj.id, "Aisle 2")
    store.add_configuration(proj.id, sys2.id, "Base case", RackConfig())

    reloaded = store.load(proj.id)
    assert reloaded.client == "ACME"
    assert len(reloaded.systems) == 2
    a1 = reloaded.system(sysm.id)
    assert len(a1.configurations) == 2
    assert {c.id for c in a1.configurations} == {"base-case", "heavier-upright"}
    # same config name in different systems is fine (separate namespaces)
    assert reloaded.system(sys2.id).configuration("base-case") is not None
    # the config round-trips back to a RackConfig
    cfg = a1.configuration(c2.id).to_rackconfig()
    assert cfg.upright_section == "UPX"

    # config.json artifact written per configuration
    cdir = store.config_dir(proj.id, sysm.id, c1.id)
    assert os.path.isfile(os.path.join(cdir, "config.json"))


def test_update_configuration_in_place(tmp_path):
    """Re-saving an existing configuration updates it; it does NOT spawn a
    new one (the 'a, a-2, a-3 ...' bug)."""
    store = ProjectStore(str(tmp_path / "projects"))
    proj = store.create_project("Job")
    sysm = store.add_system(proj.id, "Aisle 1")
    conf = store.add_configuration(proj.id, sysm.id, "A",
                                   RackConfig(n_bays=2))
    # mark a run result on it
    store.update_run_summary(proj.id, sysm.id, conf.id,
                             {"verdict": "PASS", "governing": None})

    # update the SAME id with changed parameters
    updated = store.update_configuration(proj.id, sysm.id, conf.id, "A",
                                         RackConfig(n_bays=5),
                                         notes="rev B")
    assert updated.id == conf.id                      # same id, not a-2
    reloaded = store.load(proj.id)
    assert len(reloaded.system(sysm.id).configurations) == 1   # no new entry
    c = reloaded.system(sysm.id).configuration(conf.id)
    assert c.config["n_bays"] == 5
    assert c.notes == "rev B"
    # parameters changed -> stale run result cleared
    assert c.run_summary is None

    # re-saving identical params keeps the (re-attached) run result
    store.update_run_summary(proj.id, sysm.id, conf.id, {"verdict": "PASS"})
    store.update_configuration(proj.id, sysm.id, conf.id, "A",
                              RackConfig(n_bays=5), notes="rev B")
    c = store.load(proj.id).system(sysm.id).configuration(conf.id)
    assert c.run_summary == {"verdict": "PASS"}        # unchanged -> kept
    assert len(store.load(proj.id).system(sysm.id).configurations) == 1


def test_unique_ids_and_run_summary(tmp_path):
    store = ProjectStore(str(tmp_path / "projects"))
    p1 = store.create_project("Job")
    p2 = store.create_project("Job")            # same name -> unique id
    assert p1.id != p2.id and p2.id == "job-2"

    sysm = store.add_system(p1.id, "S")
    c = store.add_configuration(p1.id, sysm.id, "C", RackConfig())
    store.add_configuration(p1.id, sysm.id, "C", RackConfig())  # -> c-2
    store.update_run_summary(p1.id, sysm.id, c.id,
                             {"verdict": "PASS", "governing": None})
    reloaded = store.load(p1.id)
    ids = [cc.id for cc in reloaded.system(sysm.id).configurations]
    assert ids == ["c", "c-2"]
    assert reloaded.system(sysm.id).configuration("c").run_summary[
        "verdict"] == "PASS"

    listed = {pr.id for pr in store.list_projects()}
    assert {"job", "job-2"} <= listed


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
