"""Cold-formed lipped-channel (single 'C') bracing sections.

Generates approximate thin-walled section properties from the dimension code
'1C{web}x{flange}x{lip}x{thickness}' (mm), so the standard 1C bracing family is
available for selection in the cross-aisle / down-aisle / spine / plan bracing
dropdowns.  Properties use the midline thin-walled line model (corners sharp);
they are editable in the section master afterwards.
"""

from __future__ import annotations

import math
import re
from typing import Dict, List, Optional, Tuple

from .model import CrossSection

# the standard 1C family (extend as needed)
STD_1C: List[str] = [
    "1C36x21x6x1.2", "1C36x21x7x1.5",
    "1C60x40x10x1.6", "1C60x40x10x2.0", "1C60x40x12x2.5",
    "1C80x40x10x1.6", "1C80x40x12x2.0",
    "1C100x50x15x2.0", "1C100x50x15x2.5",
]


def parse_1c(name: str) -> Optional[Tuple[float, float, float, float]]:
    """'1C36x21x6x1.2' -> (web h, flange b, lip c, thickness t) in mm."""
    m = re.match(r"\s*1?C\s*([\d.]+)x([\d.]+)x([\d.]+)x([\d.]+)\s*$", name,
                 re.IGNORECASE)
    if not m:
        return None
    return tuple(float(g) for g in m.groups())   # type: ignore[return-value]


def _line_props(segs: List[Tuple[Tuple[float, float], Tuple[float, float]]],
                t: float):
    """Thin-walled props from straight line segments (midline), thickness t.
    Returns (A, xc, yc, Iy, Iz) with Iy about the vertical axis (int x^2) and
    Iz about the horizontal axis (int y^2), both centroidal."""
    A = Sx = Sy = 0.0
    for (x1, y1), (x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        a = t * L
        A += a
        Sx += a * (x1 + x2) / 2.0
        Sy += a * (y1 + y2) / 2.0
    xc, yc = Sx / A, Sy / A
    Ixx = Iyy = 0.0                              # about the origin
    for (x1, y1), (x2, y2) in segs:
        L = math.hypot(x2 - x1, y2 - y1)
        Ixx += t * L * (y1 * y1 + y1 * y2 + y2 * y2) / 3.0
        Iyy += t * L * (x1 * x1 + x1 * x2 + x2 * x2) / 3.0
    Iz = Ixx - A * yc * yc                       # about horizontal centroid axis
    Iy = Iyy - A * xc * xc                       # about vertical centroid axis
    return A, xc, yc, Iy, Iz


def lipped_channel(name: str, h: float, b: float, c: float,
                   t: float, fy: float = 355.0) -> CrossSection:
    segs = [((0.0, 0.0), (0.0, h)),             # web
            ((0.0, 0.0), (b, 0.0)),             # bottom flange
            ((0.0, h), (b, h)),                 # top flange
            ((b, 0.0), (b, c)),                 # bottom lip
            ((b, h), (b, h - c))]               # top lip
    A, xc, yc, Iy, Iz = _line_props(segs, t)
    J = t ** 3 * (h + 2 * b + 2 * c) / 3.0       # open thin-walled torsion
    max_x = max(abs(0.0 - xc), abs(b - xc))
    max_y = max(abs(0.0 - yc), abs(h - yc))
    return CrossSection(
        name=name, material="steel", A=round(A, 1),
        Iy=round(Iy, 0), Iz=round(Iz, 0), J=round(J, 1),
        Wely=round(Iy / max_x, 0) if max_x else 0.0,
        Welz=round(Iz / max_y, 0) if max_y else 0.0,
        role="bracing", t=t, width_b=b, depth_h=h,
        description=f"single lipped channel {h:g}x{b:g}x{c:g}x{t:g}")


def standard_1c_sections(fy: float = 355.0) -> Dict[str, CrossSection]:
    out: Dict[str, CrossSection] = {}
    for nm in STD_1C:
        dims = parse_1c(nm)
        if dims:
            out[nm] = lipped_channel(nm, *dims, fy=fy)
    return out


# --------------------------------------------------------------------------
# Structural-mezzanine section families: 1C with corner radius, coupled 2C /
# 2x2C beams, SHS/RHS box columns and 1C floor panels (minor axis).
# --------------------------------------------------------------------------

def parse_cf_code(name: str):
    """Parse a mezzanine cold-formed section code.  Supported:

      1C{h}x{b}x{c}x{t}[r{r}]      single lipped channel (+corner radius)
      2C{h}x{b}x{c}x{t}[r{r}][B]   two channels coupled: back-to-back webs
                                   (default, I-shape) or 'B' = boxed toe-to-toe
      2x2C{h}x{b}x{c}x{t}[r{r}][B] two 2C assemblies side by side
      SHS{h}x{t} / SHS{h}x{h}x{t}  square hollow column
      RHS{h}x{b}x{t}               rectangular hollow column

    Returns (kind, dims dict) or None.  kind in {'1C','2C','2x2C','BOX'}.
    """
    s = name.strip().replace(" ", "")
    m = re.match(r"(?i)^(2x2C|2C|1C|C)([\d.]+)x([\d.]+)x([\d.]+)x([\d.]+)"
                 r"(?:r([\d.]+))?(B?)$", s)
    if m:
        kind = m.group(1).upper()
        kind = "1C" if kind == "C" else kind
        return kind, dict(h=float(m.group(2)), b=float(m.group(3)),
                          c=float(m.group(4)), t=float(m.group(5)),
                          r=float(m.group(6) or 0.0),
                          boxed=m.group(7).upper() == "B")
    m = re.match(r"(?i)^(SHS|RHS)([\d.]+)x([\d.]+)(?:x([\d.]+))?$", s)
    if m:
        h = float(m.group(2))
        if m.group(4) is None:                   # SHS{h}x{t}
            b, t = h, float(m.group(3))
        else:
            b, t = float(m.group(3)), float(m.group(4))
        if m.group(1).upper() == "SHS":
            b = h if m.group(4) is None else b
        return "BOX", dict(h=h, b=b, t=t)
    return None


# 2C back-to-back stitching convention (company standard, rarely welded):
# stitches every 500 mm along the beam; at each stitch one vertical row of
# bolts through the touching webs at 50 mm pitch, count set by the beam height
STITCH_SPACING = 500.0     # [mm] along the member
STITCH_PITCH = 50.0        # [mm] bolt pitch within the row
STITCH_EDGE = 25.0         # [mm] end distance top/bottom of the web


def stitch_bolt_count(h: float) -> int:
    """Bolts per stitch row for a beam of web height h (>= 2)."""
    return max(2, int((h - 2.0 * STITCH_EDGE) // STITCH_PITCH) + 1)


def _round_corner_delta(h: float, b: float, c: float, r: float) -> float:
    """EN 1993-1-3 5.1(3): reduction delta = 0.43 * sum(r_j * phi_j/90) /
    sum(b_p) for round corners (4 x 90-deg corners of a lipped channel).
    Gross properties are then reduced: A*(1-delta), I*(1-2*delta)."""
    if r <= 0:
        return 0.0
    n_corners = 4 if c > 0 else 2
    b_p = h + 2 * b + 2 * c
    return 0.43 * n_corners * r / max(b_p, 1.0)


def lipped_channel_r(name: str, h: float, b: float, c: float, t: float,
                     r: float = 0.0) -> CrossSection:
    """Single lipped channel with the EN 1993-1-3 round-corner reduction
    applied to the sharp-corner midline properties."""
    s = lipped_channel(name, h, b, c, t)
    d = _round_corner_delta(h, b, c, r)
    if d > 0:
        s.A = round(s.A * (1 - d), 1)
        s.Iy = round(s.Iy * (1 - 2 * d), 0)
        s.Iz = round(s.Iz * (1 - 2 * d), 0)
        s.Wely = round(s.Wely * (1 - 2 * d), 0)
        s.Welz = round(s.Welz * (1 - 2 * d), 0)
        s.description += f", corners r{r:g} (EN 1993-1-3 delta={d:.3f})"
    return s


def coupled_channel(name: str, h: float, b: float, c: float, t: float,
                    r: float = 0.0, boxed: bool = False,
                    pairs: int = 1) -> CrossSection:
    """2C / 2x2C beam composed from single lipped channels.

    Coupling per pair: back-to-back webs (I-shape, default) or 'boxed'
    toe-to-toe (lips meeting).  MAJOR axis (Iz, gravity bending with the web
    vertical) simply sums; the minor axis (Iy) uses the parallel-axis theorem
    with each channel's centroid offset from the pair centreline.  pairs=2
    places two assemblies side by side (touching), again by parallel axis.
    Torsion J is the conservative OPEN sum (stitch-bolted assembly); a
    continuously welded box may be entered in the master with its closed J.
    """
    one = lipped_channel_r("_c", h, b, c, t, r)
    # channel centroid distance from its web midline (local minor axis)
    segs_area = h + 2 * b + 2 * c
    xc = (2 * b * (b / 2.0) + 2 * c * b) / segs_area   # from web, midline
    if boxed:
        d1 = b - xc                    # webs outside, lips meet at centre
        width = 2 * b
    else:
        d1 = xc                        # webs meet at centre, flanges out
        width = 2 * b
    n1 = 2                             # channels per pair
    A = n1 * one.A
    Iz = n1 * one.Iz
    Iy = n1 * (one.Iy + one.A * d1 ** 2)
    J = n1 * one.J
    if pairs == 2:                     # two assemblies side by side
        d2 = width / 2.0
        A, Iz, J = 2 * A, 2 * Iz, 2 * J
        Iy = 2 * (Iy + (n1 * one.A) * d2 ** 2)
        width *= 2
    if boxed:
        joint = "boxed toe-to-toe"
    else:
        # standard assembly: stitch-bolted through the touching webs every
        # STITCH_SPACING, one vertical bolt row at STITCH_PITCH - the bolt
        # count follows the beam height (rarely welded).  Major-axis Iz = 2x
        # is exact regardless of stitching (equal parallel sections share the
        # neutral axis); the parallel-axis Iy and minor-axis buckling rely on
        # the stitches (EN 1993-1-1 6.4 built-up rules where slender).
        nb = stitch_bolt_count(h)
        i_min1 = math.sqrt(one.Iy / one.A)      # one channel, minor axis
        note = (f"stitch-bolted @{STITCH_SPACING:g} mm, {nb} bolts/row "
                f"@{STITCH_PITCH:g} mm pitch")
        if STITCH_SPACING > 15.0 * i_min1:
            note += (f"; spacing > 15 i_min ({15.0 * i_min1:.0f} mm) - "
                     "treat minor-axis compression as built-up "
                     "(EN 1993-1-1 6.4)")
        joint = f"back-to-back, {note}"
    sec = CrossSection(
        name=name, material="steel", A=round(A, 1), Iy=round(Iy, 0),
        Iz=round(Iz, 0), J=round(J, 1),
        Wely=round(Iy / (width / 2.0), 0),
        Welz=round(Iz / (h / 2.0), 0),
        role="beam", t=t, width_b=width, depth_h=h,
        description=(f"{'2x' if pairs == 2 else ''}2C "
                     f"{h:g}x{b:g}x{c:g}x{t:g}"
                     f"{'r%g' % r if r else ''} "
                     f"{joint}, open-J (bolted assembly)"))
    return sec


def box_section(name: str, h: float, b: float, t: float) -> CrossSection:
    """SHS/RHS column from the thin-walled midline model with the closed
    Bredt torsion constant."""
    hm, bm = h - t, b - t                        # midline dimensions
    A = 2.0 * t * (hm + bm)
    # midline rectangle: two webs (height hm) + two flanges (width bm)
    Iz = 2.0 * (t * hm ** 3 / 12.0) + 2.0 * (bm * t * (hm / 2.0) ** 2)
    Iy = 2.0 * (t * bm ** 3 / 12.0) + 2.0 * (hm * t * (bm / 2.0) ** 2)
    A0 = hm * bm                                 # enclosed midline area
    J = 4.0 * A0 ** 2 * t / (2.0 * (hm + bm))    # Bredt, uniform t
    return CrossSection(
        name=name, material="steel", A=round(A, 1), Iy=round(Iy, 0),
        Iz=round(Iz, 0), J=round(J, 0),
        Wely=round(Iy / (b / 2.0), 0), Welz=round(Iz / (h / 2.0), 0),
        role="column", t=t, width_b=b, depth_h=h,
        description=f"{'SHS' if abs(h-b) < 1e-9 else 'RHS'} "
                    f"{h:g}x{b:g}x{t:g} (closed Bredt torsion)")


def section_from_code(name: str) -> Optional[CrossSection]:
    """Resolve any mezzanine section code to a generated CrossSection
    (None when the code is not recognised)."""
    p = parse_cf_code(name)
    if p is None:
        return None
    kind, d = p
    if kind == "BOX":
        return box_section(name, d["h"], d["b"], d["t"])
    if kind == "1C":
        return lipped_channel_r(name, d["h"], d["b"], d["c"], d["t"], d["r"])
    pairs = 2 if kind == "2X2C" or kind == "2x2C" else 1
    return coupled_channel(name, d["h"], d["b"], d["c"], d["t"], d["r"],
                           boxed=d["boxed"], pairs=pairs)
