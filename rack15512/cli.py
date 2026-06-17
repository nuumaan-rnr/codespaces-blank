"""Command line interface.

Usage:
    python -m rack15512 run model.json [--outdir out] [--first-order]
    python -m rack15512 example [--outdir out] [--master sections.csv]
    python -m rack15512 sections [--master sections.csv] [--role upright]
"""

from __future__ import annotations

import argparse
import os
import sys
from typing import List

from . import io_json
from .analysis import run_all
from .builder import RackConfig, build_rack
from .checks.en15512 import all_ok, run_checks
from .library import SectionLibrary
from .model import RackModel
from .report import write_report
from .viewer import (plot_deformed, plot_diagram, plot_frame_elevation,
                     plot_model, plot_utilization)


def _run(model: RackModel, outdir: str) -> int:
    os.makedirs(outdir, exist_ok=True)
    print(f"Model '{model.name}': {len(model.nodes)} nodes, "
          f"{len(model.members)} members, "
          f"{len(model.combinations)} combinations")
    from .analysis import UnstableModelError
    try:
        cases = run_all(model)
    except UnstableModelError as exc:
        print(f"MODEL NOT STABLE: {exc}", file=sys.stderr)
        return 1
    checks = run_checks(model, cases)

    report = write_report(model, cases, checks)
    with open(os.path.join(outdir, "report.md"), "w", encoding="utf-8") as f:
        f.write(report)

    plot_model(model, os.path.join(outdir, "model.png"))
    plot_frame_elevation(model, 0.0,
                         os.path.join(outdir, "frame_elevation.png"))
    plot_utilization(model, checks, os.path.join(outdir, "utilization.png"))
    for case in cases:
        if not case.converged:
            continue
        tag = case.name.replace(" ", "_").replace("(", "").replace(")", "")
        plot_deformed(model, case, path=os.path.join(outdir, f"deformed_{tag}.png"))
        plot_diagram(model, case, "Mz", os.path.join(outdir, f"moment_{tag}.png"))
        plot_diagram(model, case, "N", os.path.join(outdir, f"axial_{tag}.png"))

    ok = all_ok(checks)
    print(f"\n{'ALL CHECKS PASS' if ok else 'CHECK FAILURES - see report'}")
    print(f"Report and plots written to {outdir}/")
    return 0 if ok else 2


def _load_library(path: str | None) -> SectionLibrary:
    return SectionLibrary.from_file(path) if path else SectionLibrary.bundled()


def _example_config(master_path: str | None) -> RackConfig:
    if master_path and master_path.lower().endswith((".xlsx", ".xlsm")):
        from .master_xlsx import load_master
        return RackConfig(master=load_master(master_path),
                          base_stiffness="auto")
    return RackConfig(library=_load_library(master_path))


def _master_cmd(a) -> int:
    from .master_store import MasterStore
    store = MasterStore(a.root)
    if a.mcmd == "import":
        m = store.import_xlsx(a.path, name=a.name, description=a.description,
                              company=a.company)
        print(f"Imported master '{m.name}' (id: {m.id}) for '{m.company}': "
              f"{len(m.sections)} sections, {len(m.base_tables)} base tables")
        return 0
    if a.mcmd == "list":
        for m in store.list():
            print(f"{m.id:24s} {m.name}  ({m.company or '-'})  "
                  f"[{len(m.sections)} sections; roles: {', '.join(m.roles())}]")
        return 0
    if a.mcmd == "show":
        m = store.load(a.master_id)
        print(f"Master: {m.name} (id: {m.id})  -  {m.description}")
        for name in m.names(a.role):
            s = m.sections[name]
            print(f"  {name:22s} {s.get('role',''):8s} "
                  f"A={s.get('A',0):8.1f}  fy={m.fy.get(name,'-')}")
        return 0
    if a.mcmd == "set":
        m = store.load(a.master_id)
        try:
            val = float(a.value)
        except ValueError:
            val = a.value
        m.update_fields(a.section, **{a.field: val})
        store.save(m)
        print(f"{a.master_id}: {a.section}.{a.field} = {val}")
        return 0
    if a.mcmd == "delete-section":
        m = store.load(a.master_id)
        m.delete_section(a.section)
        store.save(m)
        print(f"Deleted section '{a.section}' from {a.master_id}")
        return 0
    if a.mcmd == "delete":
        store.delete(a.master_id)
        print(f"Deleted master '{a.master_id}'")
        return 0
    return 1


def _project_cmd(a) -> int:
    from .project import ProjectStore, rackconfig_to_dict
    store = ProjectStore(a.root)
    if a.pcmd == "new":
        proj = store.create_project(a.name, client=a.client,
                                    location=a.location, engineer=a.engineer,
                                    description=a.description)
        print(f"Created project '{proj.name}' (id: {proj.id})")
        return 0
    if a.pcmd == "add-system":
        sysm = store.add_system(a.project_id, a.name, a.description)
        print(f"Added system '{sysm.name}' (id: {sysm.id}) to {a.project_id}")
        return 0
    if a.pcmd == "add-config":
        if a.master_id:
            from .master_store import MasterStore
            mw = MasterStore().load(a.master_id).to_workbook()
            cfg = RackConfig(master=mw, base_stiffness="auto")
        else:
            cfg = _example_config(a.master)
        conf = store.add_configuration(a.project_id, a.system_id, a.name,
                                       cfg, master_path=a.master,
                                       master_id=a.master_id, notes=a.notes)
        print(f"Added configuration '{conf.name}' (id: {conf.id})")
        return 0
    if a.pcmd == "list":
        if a.project_id:
            return _project_cmd_show(store, a.project_id)
        for proj in store.list_projects():
            n_cfg = sum(len(s.configurations) for s in proj.systems)
            print(f"{proj.id:24s} {proj.name}  "
                  f"[{len(proj.systems)} systems, {n_cfg} configs]")
        return 0
    if a.pcmd == "show":
        return _project_cmd_show(store, a.project_id)
    if a.pcmd == "run":
        from .project_run import run_configuration
        summary, cdir = run_configuration(store, a.project_id, a.system_id,
                                          a.config_id)
        gov = summary.get("governing") or {}
        print(f"{summary['verdict']} - governing "
              f"{gov.get('check')} {gov.get('target')} "
              f"= {gov.get('utilization')}")
        print(f"Artifacts in {cdir}/")
        return 0 if summary["verdict"] == "PASS" else 2
    return 1


def _project_cmd_show(store, project_id: str) -> int:
    proj = store.load(project_id)
    print(f"Project: {proj.name}  (id: {proj.id})")
    for label, val in (("Client", proj.client), ("Location", proj.location),
                       ("Engineer", proj.engineer),
                       ("Standard", proj.standard)):
        if val:
            print(f"  {label}: {val}")
    for sysm in proj.systems:
        print(f"  System '{sysm.name}' (id: {sysm.id})")
        for conf in sysm.configurations:
            rs = conf.run_summary
            status = (f"{rs['verdict']} "
                      f"(gov {rs['governing']['check']} "
                      f"{rs['governing']['utilization']})"
                      if rs and rs.get("governing") else
                      ("not run" if not rs else rs["verdict"]))
            print(f"    Config '{conf.name}' (id: {conf.id}) - {status}")
    return 0


def main(argv: List[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="rack15512",
                                description="EN 15512 storage-rack analysis "
                                            "and design checks (OpenSees, 3D)")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("run", help="analyse a model JSON file")
    pr.add_argument("model")
    pr.add_argument("--outdir", default="out")
    pr.add_argument("--first-order", action="store_true",
                    help="force linear analysis (default: second order)")

    pe = sub.add_parser("example", help="generate, save and run the demo rack")
    pe.add_argument("--outdir", default="out")
    pe.add_argument("--master", help="section master CSV/JSON/XLSX "
                                     "(default: bundled example master)")

    ps = sub.add_parser("sections", help="list the section master")
    ps.add_argument("--master", help="section master CSV/JSON/XLSX")
    ps.add_argument("--role", help="filter by role (upright/beam/bracing/...)")

    pf = sub.add_parser("rfem", help="import an RFEM data export, analyse it "
                                     "and (optionally) compare results")
    pf.add_argument("data", help="RFEM export .xlsx (1.1 Nodes, 1.7 Members, ...)")
    pf.add_argument("--master", help="section master .xlsx; recovers the "
                                     "load-dependent base springs that RFEM "
                                     "does not export")
    pf.add_argument("--fy", type=float, default=250.0,
                    help="design yield strength [MPa] (default 250)")
    pf.add_argument("--outdir", default="out_rfem")
    pf.add_argument("--compare", action="store_true",
                    help="compare member forces against the export's "
                         "'CO - 4.1' result sheets (validation.md)")
    pf.add_argument("--save-json", help="also save the imported model as JSON")

    pm = sub.add_parser("master", help="manage the in-app section masters")
    pm.add_argument("--root", default="masters",
                    help="masters directory (default: masters)")
    msub = pm.add_subparsers(dest="mcmd", required=True)
    mimp = msub.add_parser("import", help="import an Excel/CSV master once")
    mimp.add_argument("path")
    mimp.add_argument("--name")
    mimp.add_argument("--company", required=True,
                      help="owning company (mandatory; sections are "
                           "company-specific)")
    mimp.add_argument("--description", default="")
    mls = msub.add_parser("list", help="list stored masters")
    msh = msub.add_parser("show", help="show a master's sections")
    msh.add_argument("master_id")
    msh.add_argument("--role")
    mseti = msub.add_parser("set", help="update a section field")
    mseti.add_argument("master_id")
    mseti.add_argument("section")
    mseti.add_argument("field")
    mseti.add_argument("value")
    mdels = msub.add_parser("delete-section", help="remove a section")
    mdels.add_argument("master_id")
    mdels.add_argument("section")
    mdel = msub.add_parser("delete", help="delete a whole master")
    mdel.add_argument("master_id")

    pp = sub.add_parser("project", help="manage projects / systems / "
                                        "configurations")
    pp.add_argument("--root", default="projects",
                    help="projects directory (default: projects)")
    psub = pp.add_subparsers(dest="pcmd", required=True)
    pnew = psub.add_parser("new", help="create a project")
    pnew.add_argument("name")
    pnew.add_argument("--client", default="")
    pnew.add_argument("--location", default="")
    pnew.add_argument("--engineer", default="")
    pnew.add_argument("--description", default="")
    psys = psub.add_parser("add-system", help="add a system to a project")
    psys.add_argument("project_id")
    psys.add_argument("name")
    psys.add_argument("--description", default="")
    pcfg = psub.add_parser("add-config", help="add the demo/example config "
                                              "to a system")
    pcfg.add_argument("project_id")
    pcfg.add_argument("system_id")
    pcfg.add_argument("name")
    pcfg.add_argument("--master", help="external section master .xlsx/.csv")
    pcfg.add_argument("--master-id", help="stored master id (MasterStore)")
    pcfg.add_argument("--notes", default="")
    plist = psub.add_parser("list", help="list projects (or a project's tree)")
    plist.add_argument("project_id", nargs="?")
    pshow = psub.add_parser("show", help="show a project's systems / configs")
    pshow.add_argument("project_id")
    prun = psub.add_parser("run", help="run a stored configuration")
    prun.add_argument("project_id")
    prun.add_argument("system_id")
    prun.add_argument("config_id")

    a = p.parse_args(argv)
    if a.cmd == "master":
        return _master_cmd(a)
    if a.cmd == "project":
        return _project_cmd(a)
    if a.cmd == "run":
        model = io_json.load(a.model)
        if a.first_order:
            model.analysis.order = 1
        return _run(model, a.outdir)
    if a.cmd == "example":
        model = build_rack(_example_config(a.master))
        os.makedirs(a.outdir, exist_ok=True)
        io_json.save(model, os.path.join(a.outdir, "example_model.json"))
        return _run(model, a.outdir)
    if a.cmd == "rfem":
        from .master_xlsx import load_master
        from .rfem_import import load_rfem
        master = load_master(a.master) if a.master else None
        model = load_rfem(a.data, fy=a.fy, master=master)
        os.makedirs(a.outdir, exist_ok=True)
        if a.save_json:
            io_json.save(model, a.save_json)
        if not a.compare:
            return _run(model, a.outdir)
        from .analysis import run_all as _run_all
        from .rfem_compare import (compare_results, read_rfem_results,
                                   summarize)
        cases = _run_all(model)
        checks = run_checks(model, cases)
        with open(os.path.join(a.outdir, "report.md"), "w", encoding="utf-8") as f:
            f.write(write_report(model, cases, checks))
        rfem_ref = read_rfem_results(a.data)
        comps = compare_results(model, cases, rfem_ref)
        with open(os.path.join(a.outdir, "validation.md"), "w", encoding="utf-8") as f:
            f.write(summarize(comps))
        plot_model(model, os.path.join(a.outdir, "model.png"))
        plot_utilization(model, checks, os.path.join(a.outdir, "utilization.png"))
        print(f"Validation written to {a.outdir}/validation.md")
        return 0
    if a.cmd == "sections":
        lib = _load_library(a.master)
        for name in lib.names(a.role):
            s = lib.get(name)
            print(f"{s.name:20s} {s.role:10s} A={s.A:8.0f} Iy={s.Iy:.3e} "
                  f"Iz={s.Iz:.3e} J={s.J:.3e}  {s.description}")
        return 0
    return 1


if __name__ == "__main__":
    sys.exit(main())
