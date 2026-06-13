"""Project / system / configuration management.

Hierarchy:
    Project   - an engineering job (client, location, engineer, ...)
      System  - a rack system within the project (e.g. 'Aisle 1 SPR run')
        Configuration - one parameter set (a RackConfig) with its results

A project can hold many systems; a system can hold many configurations.
Everything is persisted under a `projects/` directory:

    projects/
      <project-id>/
        project.json                       # project + systems + configs
        <system-id>/
          <config-id>/
            config.json                    # the RackConfig parameters
            model.json                     # built model (after a run)
            report.md, *.png               # analysis artifacts (after a run)

Configurations store the RackConfig parameters as plain data plus a
reference to the section master file (by path); the heavy master workbook
is re-loaded on demand, never copied into the project metadata.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import re
from dataclasses import asdict, dataclass, field, fields
from typing import Any, Dict, List, Optional

from .builder import LevelSpec, RackConfig

_CFG_SKIP = {"library", "master"}     # not serialised (rebuilt from master_path)


# --------------------------------------------------------------- RackConfig IO
def rackconfig_to_dict(cfg: RackConfig) -> Dict[str, Any]:
    """Serialisable parameters of a RackConfig (without the live library /
    master objects, which are referenced separately by path)."""
    out: Dict[str, Any] = {}
    for f in fields(cfg):
        if f.name in _CFG_SKIP:
            continue
        v = getattr(cfg, f.name)
        if f.name == "levels" and v is not None:
            v = [asdict(ls) for ls in v]
        out[f.name] = v
    return out


def rackconfig_from_dict(d: Dict[str, Any], *, master=None,
                         library=None) -> RackConfig:
    known = {f.name for f in fields(RackConfig)}
    data = {k: v for k, v in d.items() if k in known and k not in _CFG_SKIP}
    levels = data.pop("levels", None)
    cfg = RackConfig(**data)
    if levels:
        cfg.levels = [LevelSpec(**ls) for ls in levels]
    cfg.master = master
    cfg.library = library
    return cfg


def _now() -> str:
    return _dt.datetime.now().isoformat(timespec="seconds")


def _slug(text: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "-", text.strip().lower()).strip("-")
    return s or "item"


# --------------------------------------------------------------- data classes
@dataclass
class Configuration:
    id: str
    name: str
    config: Dict[str, Any]                       # serialised RackConfig
    master_path: Optional[str] = None            # section master file
    notes: str = ""
    created: str = field(default_factory=_now)
    updated: str = field(default_factory=_now)
    run_summary: Optional[Dict[str, Any]] = None  # set after a run

    def to_rackconfig(self, *, master=None, library=None) -> RackConfig:
        return rackconfig_from_dict(self.config, master=master,
                                    library=library)


@dataclass
class System:
    id: str
    name: str
    description: str = ""
    created: str = field(default_factory=_now)
    configurations: List[Configuration] = field(default_factory=list)

    def configuration(self, config_id: str) -> Optional[Configuration]:
        return next((c for c in self.configurations if c.id == config_id), None)


@dataclass
class Project:
    id: str
    name: str
    client: str = ""
    location: str = ""
    engineer: str = ""
    standard: str = "EN 15512 (non-seismic)"
    description: str = ""
    created: str = field(default_factory=_now)
    systems: List[System] = field(default_factory=list)

    def system(self, system_id: str) -> Optional[System]:
        return next((s for s in self.systems if s.id == system_id), None)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Project":
        systems = []
        for s in d.get("systems", []):
            configs = [Configuration(**c) for c in s.get("configurations", [])]
            s = dict(s)
            s["configurations"] = configs
            systems.append(System(**s))
        d = dict(d)
        d["systems"] = systems
        return cls(**d)


# ------------------------------------------------------------------- store
class ProjectStore:
    """Filesystem-backed store of projects under a root directory."""

    def __init__(self, root: str = "projects"):
        self.root = root
        os.makedirs(self.root, exist_ok=True)

    # ---- paths ----------------------------------------------------------
    def _proj_dir(self, project_id: str) -> str:
        return os.path.join(self.root, project_id)

    def _proj_file(self, project_id: str) -> str:
        return os.path.join(self._proj_dir(project_id), "project.json")

    def config_dir(self, project_id: str, system_id: str,
                   config_id: str) -> str:
        return os.path.join(self._proj_dir(project_id), system_id, config_id)

    # ---- persistence ----------------------------------------------------
    def list_projects(self) -> List[Project]:
        out = []
        for name in sorted(os.listdir(self.root)):
            f = self._proj_file(name)
            if os.path.isfile(f):
                out.append(self.load(name))
        return out

    def load(self, project_id: str) -> Project:
        with open(self._proj_file(project_id)) as f:
            return Project.from_dict(json.load(f))

    def save(self, project: Project) -> None:
        os.makedirs(self._proj_dir(project.id), exist_ok=True)
        with open(self._proj_file(project.id), "w") as f:
            json.dump(project.to_dict(), f, indent=2)

    def exists(self, project_id: str) -> bool:
        return os.path.isfile(self._proj_file(project_id))

    # ---- mutation -------------------------------------------------------
    def create_project(self, name: str, **meta) -> Project:
        pid = self._unique_id(self.root, _slug(name))
        project = Project(id=pid, name=name, **meta)
        self.save(project)
        return project

    def add_system(self, project_id: str, name: str,
                   description: str = "") -> System:
        project = self.load(project_id)
        sid = self._unique_id(self._proj_dir(project_id), _slug(name),
                              taken={s.id for s in project.systems})
        system = System(id=sid, name=name, description=description)
        project.systems.append(system)
        self.save(project)
        return system

    def add_configuration(self, project_id: str, system_id: str, name: str,
                          cfg: RackConfig, master_path: Optional[str] = None,
                          notes: str = "") -> Configuration:
        project = self.load(project_id)
        system = project.system(system_id)
        if system is None:
            raise KeyError(f"system '{system_id}' not in project '{project_id}'")
        cid = self._unique_id(
            os.path.join(self._proj_dir(project_id), system_id), _slug(name),
            taken={c.id for c in system.configurations})
        conf = Configuration(id=cid, name=name,
                             config=rackconfig_to_dict(cfg),
                             master_path=master_path, notes=notes)
        system.configurations.append(conf)
        # also write a standalone config.json in the config directory
        cdir = self.config_dir(project_id, system_id, cid)
        os.makedirs(cdir, exist_ok=True)
        with open(os.path.join(cdir, "config.json"), "w") as f:
            json.dump({"name": name, "master_path": master_path,
                       "config": conf.config}, f, indent=2)
        self.save(project)
        return conf

    def update_run_summary(self, project_id: str, system_id: str,
                           config_id: str, summary: Dict[str, Any]) -> None:
        project = self.load(project_id)
        conf = project.system(system_id).configuration(config_id)
        conf.run_summary = summary
        conf.updated = _now()
        self.save(project)

    @staticmethod
    def _unique_id(parent: str, base: str,
                   taken: Optional[set] = None) -> str:
        taken = taken or set()
        cid, k = base, 2
        while cid in taken or os.path.exists(os.path.join(parent, cid)):
            cid = f"{base}-{k}"
            k += 1
        return cid


# --------------------------------------------------------------- run summary
def summarize_run(model, cases, checks) -> Dict[str, Any]:
    """Compact run record stored against a configuration."""
    from .checks.en15512 import all_ok, governing
    gov = governing(checks)
    # worst utilization per check type
    by_kind: Dict[str, float] = {}
    for c in checks:
        if c.informative:
            continue
        by_kind[c.check] = max(by_kind.get(c.check, 0.0), c.utilization)
    return {
        "run_at": _now(),
        "n_nodes": len(model.nodes),
        "n_members": len(model.members),
        "n_cases": len(cases),
        "converged": all(c.converged for c in cases),
        "verdict": "PASS" if all_ok(checks) else "FAIL",
        "governing": None if gov is None else {
            "check": gov.check, "target": gov.target,
            "set": gov.member_set, "case": gov.case,
            "utilization": round(gov.utilization, 3)},
        "max_utilization_by_check": {k: round(v, 3)
                                     for k, v in sorted(by_kind.items())},
    }
