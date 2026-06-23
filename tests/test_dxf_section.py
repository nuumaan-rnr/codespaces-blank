"""DXF -> CUFSM mesh and the thickness-weighted recentre."""

import math

import pytest

from rack15512 import dxf_section as dx
from rack15512.section_props import (recenter_to_centroid,
                                     thickness_weighted_centroid)


def _line(x0, y0, x1, y1, layer="0"):
    return (f"0\nLINE\n8\n{layer}\n10\n{x0}\n20\n{y0}\n"
            f"11\n{x1}\n21\n{y1}\n")


def _dxf(*ents):
    return "0\nSECTION\n2\nENTITIES\n" + "".join(ents) + "0\nENDSEC\n0\nEOF\n"


def test_lines_merge_into_shared_nodes():
    # a channel: web + two flanges sharing the web ends
    txt = _dxf(_line(0, 0, 0, 100),       # web
               _line(0, 100, 60, 100),    # top flange
               _line(0, 0, 60, 0))        # bottom flange
    mesh = dx.dxf_to_mesh(txt, default_t=2.0)
    assert len(mesh.nodes) == 4           # (0,0)(0,100)(60,100)(60,0)
    assert len(mesh.elems) == 3
    assert all(t == 2.0 for _i, _j, t in mesh.elems)


def test_layer_thickness_override():
    txt = _dxf(_line(0, 0, 0, 100, layer="web"),
               _line(0, 100, 60, 100, layer="flange"))
    mesh = dx.dxf_to_mesh(txt, default_t=2.0,
                          layer_thickness={"flange": 3.5})
    ts = sorted(t for _i, _j, t in mesh.elems)
    assert ts == [2.0, 3.5]
    assert mesh.layers == {"web": 1, "flange": 1}


def test_duplicate_edges_are_deduplicated():
    txt = _dxf(_line(0, 0, 10, 0), _line(10, 0, 0, 0))   # same edge twice
    mesh = dx.dxf_to_mesh(txt, default_t=1.0)
    assert len(mesh.elems) == 1


def test_arc_entity_discretised_with_endpoints():
    arc = "0\nARC\n8\n0\n10\n0\n20\n0\n40\n10\n50\n0\n51\n90\n"
    polys = dx.entity_polylines(dx.parse_dxf_entities(_dxf(arc)), seg_angle=15)
    pts = polys[0][0]
    assert len(pts) >= 6                  # 90/15 = 6 segments -> 7 points
    assert pts[0] == pytest.approx((10.0, 0.0), abs=1e-6)
    assert pts[-1] == pytest.approx((0.0, 10.0), abs=1e-6)
    # every point lies on the circle r=10
    assert all(abs(math.hypot(x, y) - 10.0) < 1e-6 for x, y in pts)


def test_bulge_segment_is_a_circular_arc():
    # quarter circle about the origin: bulge = tan(90/4 deg)
    b = math.tan(math.radians(90.0) / 4.0)
    pts = dx._bulge_points((1.0, 0.0), (0.0, 1.0), b, seg_angle=10)
    assert pts[0] == (1.0, 0.0) and pts[-1] == (0.0, 1.0)
    assert all(abs(math.hypot(x, y) - 1.0) < 1e-6 for x, y in pts)


def test_lwpolyline_open_two_segments():
    lw = ("0\nLWPOLYLINE\n8\n0\n90\n3\n70\n0\n"
          "10\n0\n20\n0\n10\n10\n20\n0\n10\n10\n20\n10\n")
    mesh = dx.dxf_to_mesh(_dxf(lw), default_t=1.5)
    assert len(mesh.nodes) == 3 and len(mesh.elems) == 2


def test_thickness_weighted_centroid_and_recenter():
    # two equal-length vertical strips, one 3x thicker -> CG pulled toward it
    nodes = {1: (0.0, 0.0), 2: (0.0, 10.0), 3: (10.0, 0.0), 4: (10.0, 10.0)}
    elems = [(1, 2, 1.0), (3, 4, 3.0)]
    xc, yc = thickness_weighted_centroid(nodes, elems)
    assert xc == pytest.approx(7.5) and yc == pytest.approx(5.0)
    moved, removed = recenter_to_centroid(nodes, elems)
    assert removed == pytest.approx((7.5, 5.0))
    assert thickness_weighted_centroid(moved, elems) == pytest.approx((0.0, 0.0))


def test_dxf_recenter_option_zeroes_cg():
    txt = _dxf(_line(0, 0, 0, 100), _line(0, 100, 60, 100),
               _line(0, 0, 60, 0))
    mesh = dx.dxf_to_mesh(txt, default_t=2.0, recenter=True)
    assert mesh.centroid_removed is not None
    cg = thickness_weighted_centroid(mesh.nodes, mesh.elems)
    assert cg == pytest.approx((0.0, 0.0), abs=1e-6)


def test_per_element_layers_and_equivalent_thickness():
    txt = _dxf(_line(0, 0, 0, 100, layer="web"),
               _line(0, 100, 60, 100, layer="flange"),
               _line(0, 0, 60, 0, layer="flange"))
    mesh = dx.dxf_to_mesh(txt, default_t=2.0)
    assert len(mesh.elem_layers) == len(mesh.elems) == 3
    assert mesh.elem_layers.count("flange") == 2
    # override each element's equivalent (reduced) thickness individually
    mesh2 = mesh.with_thicknesses([1.0, 1.5, 1.8])
    assert [t for _i, _j, t in mesh2.elems] == [1.0, 1.5, 1.8]
    assert [t for _i, _j, t in mesh.elems] == [2.0, 2.0, 2.0]   # original intact
    with pytest.raises(ValueError):
        mesh.with_thicknesses([1.0])           # wrong count


def test_recenter_uses_per_element_equivalent_thickness():
    from rack15512.section_props import thickness_weighted_centroid
    # two equal vertical strips; make the right one's equivalent t larger
    txt = _dxf(_line(0, 0, 0, 10), _line(10, 0, 10, 10))
    mesh = dx.dxf_to_mesh(txt, default_t=1.0).with_thicknesses([1.0, 3.0])
    xc, _yc = thickness_weighted_centroid(mesh.nodes, mesh.elems)
    assert xc == pytest.approx(7.5)            # pulled toward the thicker element


def test_round_trip_into_cufsm_properties():
    from rack15512 import cufsm
    txt = _dxf(_line(0, 0, 0, 100), _line(0, 100, 60, 100),
               _line(0, 0, 60, 0))
    mesh = dx.dxf_to_mesh(txt, default_t=2.0)
    nodes, elems = cufsm.parse_cufsm_model(
        dx.mesh_to_cufsm_text(mesh).splitlines())
    assert len(nodes) == len(mesh.nodes) and len(elems) == len(mesh.elems)
    props = cufsm.properties_from_cufsm((nodes, elems))
    assert props.A == pytest.approx((100 + 60 + 60) * 2.0, rel=1e-9)
