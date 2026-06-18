"""Combine an upright and a bolted stiffener into one MONOLITHIC cross-section.

A reinforcement bolted to a cold-formed upright acts compositely.  Modelling it
as a separate offset member tied with rigid links turns the pair into a battened
built-up column whose rigid battens induce spurious local chord moments.  The
clean, artifact-free model is a single combined section: the two profiles are
merged by the parallel-axis theorem about their combined centroid, and that
section is assigned to the reinforced upright segments.  Load and moments then
flow through the combined centroid - area and the cross-aisle inertia rise, so
the flexural-buckling resistance increases and the utilisation drops.

`offset` is the centroid separation between the upright and the stiffener,
measured in the CROSS-AISLE direction (the local-y / Lcr_y axis of the buckling
check), i.e. the axis the reinforcement is meant to strengthen.

NOTE: these are an engineering parallel-axis ESTIMATE.  For a verified reinforced-
upright capacity, supply a tested / section-software compound section as a master
and set `offset` to the real centroid separation of the assembly.
"""

from __future__ import annotations

import math

from .model import CrossSection


def combined_section(name: str, up: CrossSection, st: CrossSection,
                     offset: float, material: str) -> CrossSection:
    """Upright `up` + stiffener `st` merged about the combined centroid, the two
    centroids `offset` mm apart in the cross-aisle (local-y) direction."""
    A = up.A + st.A
    c = st.A * offset / A if A > 0 else 0.0      # combined CoG from the upright
    d_up, d_st = c, offset - c

    iy_up = up.Iy_gross if up.Iy_gross is not None else up.Iy
    iy_st = st.Iy_gross if st.Iy_gross is not None else st.Iy
    iz_up = up.Iz_gross if up.Iz_gross is not None else up.Iz
    iz_st = st.Iz_gross if st.Iz_gross is not None else st.Iz
    # cross-aisle (local y): parallel-axis boost from the centroid separation
    Iy = iy_up + up.A * d_up ** 2 + iy_st + st.A * d_st ** 2
    # down-aisle (local z): no offset that way -> simple sum
    Iz = iz_up + iz_st
    J = (up.J or 0.0) + (st.J or 0.0)

    # extreme-fibre distance in cross-aisle for the combined section modulus
    half_up = 0.5 * (up.width_b or up.depth_h or 2.0 * math.sqrt(max(iy_up, 1.0)
                                                                 / max(up.A, 1.0)))
    half_st = 0.5 * (st.width_b or st.depth_h or 2.0 * math.sqrt(max(iy_st, 1.0)
                                                                 / max(st.A, 1.0)))
    c_ext = max(d_up + half_up, d_st + half_st, 1.0)
    Wely = Iy / c_ext
    Welz = (up.Welz or 0.0) + (st.Welz or 0.0)

    a_eff = up.area_eff + st.area_eff
    return CrossSection(
        name=name, material=material, A=A, Iy=Iy, Iz=Iz, J=J,
        Wely=Wely, Welz=Welz,
        A_eff=a_eff, Wy_eff=Wely, Wz_eff=Welz,
        buckling_curve_y=up.buckling_curve_y, buckling_curve_z=up.buckling_curve_z,
        role="upright",
        description=f"combined {up.name}+{st.name} @ {offset:.0f} mm (parallel-axis)",
        t=up.t, e1=up.e1, e2=up.e2, fu=up.fu,
        width_b=(up.width_b or 0.0) + offset, depth_h=up.depth_h,
        # FT/warping of a built-up section is out of scope -> leave None so the
        # buckling check uses flexural buckling only (conservative)
        It_gross=None, Iw_gross=None, y0=None,
        Iy_gross=Iy, Iz_gross=Iz)
