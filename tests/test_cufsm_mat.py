"""CUFSM .mat export: structure matches a real CUFSM input, effective
thickness comes through, and it round-trips via scipy.io.loadmat."""

import io

import pytest

from rack15512 import cufsm_mat

sio = pytest.importorskip("scipy.io")        # .mat needs SciPy


def _channel():
    # web + two flanges, per-element (effective) thicknesses 2.0 / 1.6 / 1.6
    nodes = {1: (0.0, 0.0), 2: (0.0, 100.0), 3: (60.0, 100.0), 4: (60.0, 0.0)}
    elems = [(1, 2, 2.0), (2, 3, 1.6), (1, 4, 1.6)]
    return nodes, elems


def test_mat_has_cufsm_variables_and_shapes():
    nodes, elems = _channel()
    data = sio.loadmat(io.BytesIO(
        cufsm_mat.cufsm_mat_bytes(nodes, elems, E=210000.0, nu=0.3, fy=450.0)))
    assert {"prop", "node", "elem", "lengths", "springs",
            "constraints"} <= set(data)
    assert data["prop"].shape == (1, 6)
    assert data["node"].shape == (4, 8)      # [#, x, y, 4 dofs, stress]
    assert data["elem"].shape == (3, 5)      # [#, i, j, t, matnum]


def test_one_based_numbering_and_free_dofs():
    nodes, elems = _channel()
    d = sio.loadmat(io.BytesIO(cufsm_mat.cufsm_mat_bytes(nodes, elems)))
    node, elem = d["node"], d["elem"]
    assert list(node[:, 0]) == [1, 2, 3, 4]              # 1-based node ids
    assert (node[:, 3:7] == 1).all()                     # all DOFs free
    assert list(elem[:, 0]) == [1, 2, 3]                 # 1-based elem ids
    assert elem[:, 1].min() == 1 and elem[:, 2].max() == 4
    # prop / elem material ids agree
    assert elem[0, 4] == d["prop"][0, 0]


def test_effective_thickness_in_elem_matrix():
    nodes, elems = _channel()
    d = sio.loadmat(io.BytesIO(cufsm_mat.cufsm_mat_bytes(nodes, elems)))
    assert sorted(d["elem"][:, 3]) == [1.6, 1.6, 2.0]    # per-element t


def test_material_and_reference_stress():
    nodes, elems = _channel()
    d = sio.loadmat(io.BytesIO(
        cufsm_mat.cufsm_mat_bytes(nodes, elems, E=203000.0, nu=0.3, fy=355.0)))
    prop = d["prop"][0]
    assert prop[1] == pytest.approx(203000.0) and prop[2] == pytest.approx(203000.0)
    assert prop[5] == pytest.approx(203000.0 / (2 * 1.3))     # G
    assert list(d["node"][:, 7]) == pytest.approx([355.0] * 4)   # ref stress=fy


def test_lengths_present_and_increasing():
    nodes, elems = _channel()
    d = sio.loadmat(io.BytesIO(cufsm_mat.cufsm_mat_bytes(nodes, elems)))
    L = d["lengths"].ravel()
    assert len(L) >= 20 and L[0] < L[-1]


def test_write_to_path(tmp_path):
    nodes, elems = _channel()
    p = tmp_path / "upright.mat"
    cufsm_mat.write_cufsm_mat(str(p), nodes, elems)
    assert p.exists()
    assert "elem" in sio.loadmat(str(p))
