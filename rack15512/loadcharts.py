"""Load-chart generator for uprights and beams.

ADDITIVE only - this module imports the frozen analysis engine and never edits
it.  It produces, from a section master:

  * Upright load charts - max axial buckling capacity N_b,Rd (EN 15512, the same
    closed form as rack15512.presize.upright_utilisation) versus the down-aisle
    buckling length Lcr_DA, for cross-aisle pitches 500/600 mm, in three configs:
      - X  : crossed bracing, the upright is restrained every panel  -> Lcr_CA = pitch
      - D  : single-diagonal bracing, restrained every other panel    -> Lcr_CA = 2*pitch
      - XS : X bracing + an internal stiffener combined with the upright (90-deep
             upright + IN_STIFFENER90X1.6, 120-deep + IN_STIFFENER120X1.6).
    Uprights are charted at fy = 355 (pure axial - a strut load chart).

  * Beam load charts - max total load per bay level (the pair of beams) versus the
    span, for a single-span beam with semi-rigid end connectors.  The connector
    rotational stiffness depends on the UPRIGHT thickness it bolts to, so a curve
    is drawn per upright thickness.  Governed by the min of beam bending, the
    connector moment, deflection (L/200) and shear.

Outputs PNG charts (matplotlib) and tidy Excel tables (openpyxl).

CLI:  python -m rack15512.loadcharts --master <master.xlsx> --out charts/
"""

from __future__ import annotations

import argparse
import math
import os
import zipfile
from dataclasses import replace
from typing import Dict, List, Optional, Tuple

from . import branding
from .builder import _closed_upright_section
from .master_xlsx import load_master
from .model import CrossSection, Steel
from .presize import upright_utilisation

# ----------------------------------------------------------------- constants
E_STEEL = 210000.0          # MPa
G_STEEL = 81000.0           # MPa
GAMMA_M0 = 1.0              # cross-section resistance (EN 15512)
GAMMA_M1 = 1.1              # member buckling resistance (EN 15512)
FY_UPRIGHT = 355.0          # YS355, per the request
DEFL_RATIO = 200.0          # beam deflection limit L / 200 (EN 15512 SLS)

UP_DA = list(range(250, 5001, 50))        # down-aisle buckling length grid [mm]
BEAM_SPAN = list(range(500, 4001, 50))    # beam span grid [mm]
PITCHES = (500.0, 600.0)                   # cross-aisle bracing pitches [mm]

# config name -> (matplotlib colour, linestyle)
_STYLE = {
    "X-500": (branding.TEAL, "-"),
    "X-600": (branding.TEAL_LIGHT, "-"),
    "D-1000": (branding.GREY, "--"),
    "D-1200": (branding.GREY_LIGHT, "--"),
    "XS-500": ("#C0392B", "-"),
    "XS-600": ("#E67E22", "-"),
}
_BEAM_COLOURS = [branding.TEAL, "#C0392B", "#E67E22", branding.GREY,
                 branding.TEAL_LIGHT, "#8E44AD"]


# ------------------------------------------------------- combined (XS) section
def combined_upright_section(up: CrossSection, st: CrossSection,
                             offset: float) -> CrossSection:
    """Upright + internal stiffener as ONE section, parallel-axis about the
    combined centroid in the cross-aisle (Iy / Lcr_CA) direction, with the
    closed-cell torsion/warping/shear-centre credit from the Type-1 stiffener.

    `offset` = cross-aisle centroid separation [mm] (the stiffener mount_offset).
    The cross-aisle inertia gains the parallel-axis term (the lever the stiffener
    adds); the down-aisle inertia is a simple sum (no lever that way)."""
    A = up.A + st.A
    a_eff = up.area_eff + st.area_eff
    c = st.A * offset / A                       # centroid shift toward the stiffener
    Iy = up.Iy + up.A * c ** 2 + st.Iy + st.A * (offset - c) ** 2
    Iz = up.Iz + st.Iz
    closed = _closed_upright_section(up.name + "~closed", up)   # closed-cell It/Iw/y0
    return replace(up, name=f"{up.name}+{st.name}", A=A, A_eff=a_eff,
                   Iy=Iy, Iz=Iz, Iy_gross=Iy, Iz_gross=Iz,
                   It_gross=closed.It_gross, Iw_gross=closed.Iw_gross,
                   y0=closed.y0, J=closed.J)


def _stiffener_for(lib, up: CrossSection) -> Optional[CrossSection]:
    """The matching internal stiffener (1.6 mm) for a 90/120-deep upright."""
    h = round(up.depth_h or 0.0)
    name = {90: "IN_STIFFENER90X1.6", 120: "IN_STIFFENER120X1.6"}.get(h)
    if not name:
        return None
    try:
        return lib.get(name)
    except (KeyError, ValueError):
        return None


# ------------------------------------------------------------- upright capacity
def upright_capacity_kN(sec: CrossSection, fy: float, Lcr_da: float,
                        Lcr_ca: float) -> Tuple[float, str]:
    """Pure-axial buckling capacity N_b,Rd [kN] and the governing axis
    ('y'=cross-aisle, 'z'=down-aisle, 'FT')."""
    mat = Steel("steel", E=E_STEEL, fy=fy, G=G_STEEL)
    u = upright_utilisation(sec, mat, Lcr_y=Lcr_ca, Lcr_z=Lcr_da, N=1.0,
                            gamma_M1=GAMMA_M1, gamma_M0=GAMMA_M0)
    return u["N_b_Rd"] / 1e3, u["gov"]


def _upright_configs(lib, up: CrossSection
                     ) -> List[Tuple[str, float, CrossSection]]:
    """(label, Lcr_CA, section) for every config of one upright."""
    cfgs: List[Tuple[str, float, CrossSection]] = []
    for p in PITCHES:                       # X: braced every panel -> Lcr_CA = pitch
        cfgs.append((f"X-{int(p)}", p, up))
    for p in PITCHES:                       # D: every other panel  -> Lcr_CA = 2*pitch
        cfgs.append((f"D-{int(2 * p)}", 2 * p, up))
    st = _stiffener_for(lib, up)            # XS: combined section (90/120 only)
    if st is not None:
        comb = combined_upright_section(up, st, st.mount_offset or 30.0)
        for p in PITCHES:
            cfgs.append((f"XS-{int(p)}", p, comb))
    return cfgs


def upright_chart_data(lib, fy: float = FY_UPRIGHT) -> Dict[str, dict]:
    """{upright_name: {"desc":..., "curves": {label: {"lcr_ca":, "da":[...],
    "cap":[...], "gov":[...]}}}}."""
    out: Dict[str, dict] = {}
    for name in lib.names("upright"):
        up = lib.get(name)
        curves: Dict[str, dict] = {}
        for label, lcr_ca, sec in _upright_configs(lib, up):
            caps, govs = [], []
            for da in UP_DA:
                cap, gov = upright_capacity_kN(sec, fy, da, lcr_ca)
                caps.append(cap)
                govs.append(gov)
            curves[label] = {"lcr_ca": lcr_ca, "da": UP_DA, "cap": caps,
                             "gov": govs}
        out[name] = {"desc": up.description or "", "curves": curves}
    return out


# --------------------------------------------------------------- beam capacity
def beam_level_capacity_kN(beam: CrossSection, fy: float, span: float,
                           k_conn: Optional[float], m_rd: Optional[float]
                           ) -> Tuple[float, str]:
    """Max TOTAL load per bay level (both beams) [kN] for a single-span beam with
    equal semi-rigid end rotational springs of stiffness k_conn [N*mm/rad].

    Returns (load_kN, governing) where governing is one of bending / connector /
    deflection / shear.  Load is shared by the two beams: total = 2 * w * span."""
    L = span
    EI = E_STEEL * beam.Iz                       # strong (down-aisle gravity) axis
    # connection fixity factor: gamma=0 pinned, gamma=1 fully fixed
    gamma = 1.0 / (1.0 + 2.0 * EI / (k_conn * L)) if (k_conn and k_conn > 0) else 0.0
    inf = float("inf")
    lim: Dict[str, float] = {}

    # beam bending: max of mid-span (wL^2(1/8 - g/12)) and end (wL^2 * g/12)
    coef_mid = 1.0 / 8.0 - gamma / 12.0
    coef_end = gamma / 12.0
    coef_bend = max(coef_mid, coef_end)
    m_rd_beam = beam.mod_z_eff * fy / GAMMA_M0
    lim["bending"] = m_rd_beam / (coef_bend * L * L) if coef_bend > 0 else inf

    # connector moment: end moment <= connector design resistance
    lim["connector"] = (m_rd / (coef_end * L * L)
                        if (m_rd and coef_end > 1e-12) else inf)

    # deflection L/200 (bending + shear when Avz given)
    cb = L ** 4 / EI * (5.0 / 384.0 - gamma / 96.0)
    cs = L * L / (8.0 * G_STEEL * beam.Avz) if beam.Avz else 0.0
    lim["deflection"] = (L / DEFL_RATIO) / (cb + cs) if (cb + cs) > 0 else inf

    # shear: V = wL/2 <= V_Rd = A_v fy / (sqrt3 gM0), A_v = 2 h t (two webs)
    if beam.depth_h and beam.t:
        v_rd = 2.0 * beam.depth_h * beam.t * fy / (math.sqrt(3.0) * GAMMA_M0)
        lim["shear"] = 2.0 * v_rd / L

    w = min(lim.values())                        # per beam [N/mm]
    gov = min(lim, key=lim.get)
    return 2.0 * w * L / 1e3, gov                # both beams -> total kN per level


def _beam_thickness_curves(beam: CrossSection
                           ) -> List[Tuple[Optional[float], float]]:
    """(upright_thickness, connector_k) pairs; falls back to the single k."""
    if beam.connector_k_by_upl:
        return [(float(t), float(k)) for t, k in beam.connector_k_by_upl]
    if beam.connector_k:
        return [(None, float(beam.connector_k))]
    return [(None, 0.0)]                          # pinned (no connector data)


def beam_chart_data(lib, fy_of) -> Dict[str, dict]:
    """{beam_name: {"fy":, "m_rd":, "curves": {upright_t: {"span":[...],
    "load":[...], "gov":[...]}}}}."""
    out: Dict[str, dict] = {}
    for name in lib.names("beam"):
        beam = lib.get(name)
        fy = fy_of(name)
        m_rd = beam.connector_m_rd
        curves: Dict[str, dict] = {}
        for t, k in _beam_thickness_curves(beam):
            loads, govs = [], []
            for L in BEAM_SPAN:
                load, gov = beam_level_capacity_kN(beam, fy, L, k, m_rd)
                loads.append(load)
                govs.append(gov)
            key = f"upl {t:.1f} mm" if t else "pinned"
            curves[key] = {"span": BEAM_SPAN, "load": loads, "gov": govs}
        out[name] = {"fy": fy, "m_rd": m_rd, "curves": curves}
    return out


# ------------------------------------------------------------------- plotting
def _plot_upright(name: str, info: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for label, c in info["curves"].items():
        colour, ls = _STYLE.get(label, (branding.GREY, "-"))
        ax.plot(c["da"], c["cap"], ls, color=colour, lw=1.8,
                label=f"{label}  (Lcr,CA={int(c['lcr_ca'])})")
    ax.set_xlabel("Down-aisle buckling length  Lcr,DA  [mm]")
    ax.set_ylabel("Axial capacity  N_b,Rd  [kN]")
    ax.set_title(f"{name}  -  {info['desc']}\nUpright load chart  ·  fy=355  ·  "
                 f"γM1=1.1  (X=pitch, D=2×pitch, XS=+internal stiffener)",
                 fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8, ncol=2)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


def _plot_beam(name: str, info: dict, path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    for i, (key, c) in enumerate(info["curves"].items()):
        colour = _BEAM_COLOURS[i % len(_BEAM_COLOURS)]
        ax.plot(c["span"], c["load"], "-", color=colour, lw=1.8,
                label=f"upright {key}")
    ax.set_xlabel("Beam span  [mm]")
    ax.set_ylabel("Max load per bay level (pair of beams)  [kN]")
    ax.set_title(f"{name}  -  beam load chart  ·  fy={info['fy']:.0f}  ·  "
                 f"deflection L/200\n(semi-rigid connectors; curve per upright "
                 f"thickness)", fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(bottom=0)
    ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=130)
    plt.close(fig)


# --------------------------------------------------------------------- Excel
def _write_upright_xlsx(data: Dict[str, dict], path: str) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Uprights"
    ws.append(["section", "description", "config", "Lcr_CA_mm", "Lcr_DA_mm",
               "capacity_kN", "governing"])
    for name, info in data.items():
        for label, c in info["curves"].items():
            for da, cap, gov in zip(c["da"], c["cap"], c["gov"]):
                ws.append([name, info["desc"], label, int(c["lcr_ca"]), da,
                           round(cap, 2), gov])
    wb.save(path)


def _write_beam_xlsx(data: Dict[str, dict], path: str) -> None:
    import openpyxl
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Beams"
    ws.append(["beam", "fy_MPa", "upright_thickness", "span_mm",
               "load_per_level_kN", "governing"])
    for name, info in data.items():
        for key, c in info["curves"].items():
            for sp, load, gov in zip(c["span"], c["load"], c["gov"]):
                ws.append([name, round(info["fy"], 0), key, sp,
                           round(load, 2), gov])
    wb.save(path)


# ----------------------------------------------------------------- generation
def generate(master_path: str, out_dir: str) -> dict:
    """Generate all upright and beam load charts + tables under out_dir.
    Returns a summary dict with the output paths."""
    mw = load_master(master_path)
    lib = mw.library

    up_dir = os.path.join(out_dir, "uprights")
    bm_dir = os.path.join(out_dir, "beams")
    os.makedirs(up_dir, exist_ok=True)
    os.makedirs(bm_dir, exist_ok=True)

    up_data = upright_chart_data(lib, fy=FY_UPRIGHT)
    for name, info in up_data.items():
        _plot_upright(name, info, os.path.join(up_dir, f"{name}.png"))
    up_xlsx = os.path.join(out_dir, "Upright_Load_Charts.xlsx")
    _write_upright_xlsx(up_data, up_xlsx)

    def fy_of(beam_name: str) -> float:
        return float(mw.fy.get(beam_name, FY_UPRIGHT) or FY_UPRIGHT)

    bm_data = beam_chart_data(lib, fy_of)
    for name, info in bm_data.items():
        safe = name.replace("/", "_")
        _plot_beam(name, info, os.path.join(bm_dir, f"{safe}.png"))
    bm_xlsx = os.path.join(out_dir, "Beam_Load_Charts.xlsx")
    _write_beam_xlsx(bm_data, bm_xlsx)

    # zip the PNGs for delivery
    png_zip = os.path.join(out_dir, "load_charts_png.zip")
    with zipfile.ZipFile(png_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for d, sub in ((up_dir, "uprights"), (bm_dir, "beams")):
            for f in sorted(os.listdir(d)):
                if f.endswith(".png"):
                    z.write(os.path.join(d, f), f"{sub}/{f}")

    return {"uprights": len(up_data), "beams": len(bm_data),
            "upright_xlsx": up_xlsx, "beam_xlsx": bm_xlsx, "png_zip": png_zip,
            "out_dir": out_dir}


def main(argv: Optional[List[str]] = None) -> None:
    ap = argparse.ArgumentParser(description="Generate upright & beam load charts.")
    ap.add_argument("--master", required=True, help="section master .xlsx")
    ap.add_argument("--out", default="charts", help="output directory")
    args = ap.parse_args(argv)
    summary = generate(args.master, args.out)
    print(f"uprights: {summary['uprights']} charts, beams: {summary['beams']} charts")
    print(f"  {summary['upright_xlsx']}")
    print(f"  {summary['beam_xlsx']}")
    print(f"  {summary['png_zip']}")


if __name__ == "__main__":
    main()
