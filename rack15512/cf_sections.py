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
