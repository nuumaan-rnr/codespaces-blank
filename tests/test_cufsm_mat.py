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


def _results_mat_bytes(curve, with_geometry=True):
    import numpy as np
    data = {"curve": curve, "lengths": np.array([c[0, 0] for c in curve])}
    if with_geometry:
        # our exported .mat geometry: uniform stress = 100 (so P_ref = 100*A)
        data["node"] = np.array([[1, 0, 0, 1, 1, 1, 1, 100.0],
                                 [2, 0, 100, 1, 1, 1, 1, 100.0]])
        data["elem"] = np.array([[1, 1, 2, 2.0, 100]])      # A = 2*100 = 200
    buf = io.BytesIO()
    sio.savemat(buf, data)
    return buf.getvalue()


def test_read_results_array_curve():
    import numpy as np
    # (n_len, 2, n_modes): [:,0,0]=half-wavelength, [:,1,0]=lowest-mode LF
    hw = [10.0, 50.0, 90.0, 200.0, 400.0]
    lf = [2.0, 0.9, 1.5, 1.1, 1.3]            # local min at hw=50
    curve = np.zeros((5, 2, 4))
    for i in range(5):
        curve[i, 0, :] = hw[i]
        curve[i, 1, :] = lf[i] + np.arange(4)  # mode 0 lowest
    res = cufsm_mat.read_results_mat(_results_mat_bytes(curve))
    assert res["half_wavelengths"] == pytest.approx(hw)
    assert res["signature"] == pytest.approx(lf)
    assert res["reference_load"] == pytest.approx(100.0 * 200.0)   # fy * A

    # the signature feeds the usual minima extraction -> Pcr
    from rack15512 import cufsm
    loads = cufsm.loads_from_signature(res["half_wavelengths"], res["signature"],
                                       reference=res["reference_load"])
    assert loads.Pcrl == pytest.approx(0.9 * 100.0 * 200.0)         # LF_local * P_ref


def test_read_curve_object_cell_format():
    # CUFSM's older object/cell layout: curve[i] = [[hw, lf_mode0], [hw, lf1]...]
    import numpy as np
    cells = np.empty(3, dtype=object)
    for i, (h, v) in enumerate([(20.0, 1.4), (60.0, 0.8), (300.0, 1.2)]):
        cells[i] = np.array([[h, v], [h, v + 1.0]])      # lowest mode first
    hw, lf = cufsm_mat._read_curve(cells.reshape(3, 1))
    assert hw == pytest.approx([20.0, 60.0, 300.0])
    assert lf == pytest.approx([1.4, 0.8, 1.2])


def test_read_results_requires_curve():
    buf = io.BytesIO()
    sio.savemat(buf, {"node": [[1, 0, 0, 1, 1, 1, 1, 1]]})
    with pytest.raises(ValueError):
        cufsm_mat.read_results_mat(buf.getvalue())
