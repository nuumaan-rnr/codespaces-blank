"""Write a CUFSM-native ``.mat`` file for a cross-section mesh.

Produces a MATLAB ``.mat`` that opens directly in the `CUFSM
<https://www.ce.jhu.edu/cufsm/>`_ GUI - the variables, columns and 1-based
numbering match a real CUFSM input file (verified against the bundled CUFSM
``lippedc_test.mat``):

* ``prop``        ``[matnum, Ex, Ey, vx, vy, G]``
* ``node``        ``[node#, x, z, xdof, zdof, ydof, qdof, stress]`` (DOFs free)
* ``elem``        ``[elem#, node_i, node_j, t, matnum]`` - **t is the per-element
                  (effective / reduced) thickness**, so a perforated upright's
                  equivalent thicknesses come straight through
* ``lengths``     half-wavelengths for the signature curve
* ``springs`` / ``constraints``  ``0`` (none)

This is an *export* - it does not run CUFSM (use the MATLAB CUFSM to analyse).
Writing needs SciPy (``pip install scipy``); the function raises a clear message
if it is missing.
"""

from __future__ import annotations

import io
import math
from typing import Dict, List, Optional, Sequence, Tuple

__all__ = ["build_cufsm_vars", "write_cufsm_mat", "cufsm_mat_bytes",
           "recommend_lengths", "read_results_mat"]

Point = Tuple[float, float]
MATNUM = 100                       # material id (mirrors CUFSM's template files)


def _require_scipy():
    try:
        import scipy.io as sio
        return sio
    except ImportError as exc:      # pragma: no cover - environment dependent
        raise ImportError(
            "writing a CUFSM .mat needs SciPy - install it with "
            "'pip install scipy'") from exc


def recommend_lengths(nodes: Dict[int, Point],
                      elems: Sequence[Tuple[int, int, float]],
                      n: int = 50) -> List[float]:
    """A log-spaced set of half-wavelengths spanning local -> global buckling,
    from the section's smallest element to several times its overall size."""
    xs = [p[0] for p in nodes.values()]
    ys = [p[1] for p in nodes.values()]
    size = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    d_min = min((math.hypot(nodes[j][0] - nodes[i][0],
                            nodes[j][1] - nodes[i][1])
                 for i, j, _t in elems), default=size)
    lo = max(2.0, 0.4 * d_min)
    hi = max(10.0 * lo, 6.0 * size, 1000.0)
    return [lo * (hi / lo) ** (k / (n - 1)) for k in range(n)]


def build_cufsm_vars(nodes: Dict[int, Point],
                     elems: Sequence[Tuple[int, int, float]],
                     E: float = 210000.0, nu: float = 0.3, fy: float = 355.0,
                     ref_stress: Optional[float] = None,
                     lengths: Optional[Sequence[float]] = None) -> dict:
    """Build the CUFSM ``.mat`` variable dictionary from a node/element mesh.

    ``elems`` carry each element's (effective) thickness.  ``ref_stress`` is the
    uniform reference longitudinal stress in the node matrix (compression);
    defaults to ``fy`` so the signature curve's critical stress is relative to
    yield.  Node and element numbers are written 1-based (MATLAB convention).
    """
    import numpy as np
    if ref_stress is None:
        ref_stress = fy
    G = E / (2.0 * (1.0 + nu))
    ids = sorted(nodes)
    remap = {nid: k + 1 for k, nid in enumerate(ids)}          # 1-based
    node = np.array([[remap[nid], nodes[nid][0], nodes[nid][1],
                      1, 1, 1, 1, ref_stress] for nid in ids], dtype=float)
    elem = np.array([[k + 1, remap[i], remap[j], float(t), MATNUM]
                     for k, (i, j, t) in enumerate(elems)], dtype=float)
    prop = np.array([[MATNUM, E, E, nu, nu, G]], dtype=float)
    if lengths is None:
        lengths = recommend_lengths(nodes, elems)
    L = np.array(list(lengths), dtype=float).reshape(-1, 1)
    return {"prop": prop, "node": node, "elem": elem, "lengths": L,
            "springs": np.array([[0]]), "constraints": np.array([[0]])}


def write_cufsm_mat(path: str, nodes: Dict[int, Point],
                    elems: Sequence[Tuple[int, int, float]], **kwargs) -> None:
    """Write a CUFSM ``.mat`` file to ``path`` (see :func:`build_cufsm_vars`)."""
    sio = _require_scipy()
    sio.savemat(path, build_cufsm_vars(nodes, elems, **kwargs))


def cufsm_mat_bytes(nodes: Dict[int, Point],
                    elems: Sequence[Tuple[int, int, float]], **kwargs) -> bytes:
    """The CUFSM ``.mat`` as bytes (for a download button)."""
    sio = _require_scipy()
    buf = io.BytesIO()
    sio.savemat(buf, build_cufsm_vars(nodes, elems, **kwargs))
    return buf.getvalue()


# ---------------------------------------------------------- read CUFSM results
def _read_curve(curve) -> Tuple[List[float], List[float]]:
    """Signature curve (half-wavelength, lowest-mode load factor) from CUFSM's
    ``curve`` results, in either layout: an ``(n_len, 2, n_modes)`` array
    (``[:,0,0]`` = half-wavelengths, ``[:,1,0]`` = lowest-mode load factor) or
    the older object/cell array of ``[n_modes, 2]`` matrices."""
    import numpy as np
    c = np.array(curve)
    hw: List[float] = []
    lf: List[float] = []
    if c.dtype == object:
        flat = c.ravel()
        for cell in flat:
            cell = np.array(cell)
            if cell.ndim == 2 and cell.shape[0] >= 1 and cell.shape[1] >= 2:
                hw.append(float(cell[0, 0]))
                lf.append(float(cell[0, 1]))
    elif c.ndim == 3 and c.shape[1] >= 2:
        hw = [float(x) for x in c[:, 0, 0]]
        lf = [float(x) for x in c[:, 1, 0]]
    elif c.ndim == 2 and c.shape[1] >= 2:
        hw = [float(x) for x in c[:, 0]]
        lf = [float(x) for x in c[:, 1]]
    if not hw:
        raise ValueError("could not parse the CUFSM 'curve' results")
    return hw, lf


def _reference_load(mat: dict) -> Optional[float]:
    """The applied reference axial load = integral of the node stress over the
    section (sum of mean-element-stress x thickness x length), so a load factor
    times this gives the buckling load.  None if node/elem are absent."""
    import numpy as np
    if "node" not in mat or "elem" not in mat:
        return None
    node = np.array(mat["node"], dtype=float)
    elem = np.array(mat["elem"], dtype=float)
    if node.ndim != 2 or node.shape[1] < 3:
        return None
    stress = {int(round(r[0])): float(r[-1]) for r in node}
    coord = {int(round(r[0])): (float(r[1]), float(r[2])) for r in node}
    total = 0.0
    for e in elem:
        i, j, t = int(round(e[1])), int(round(e[2])), float(e[3])
        if i in coord and j in coord:
            L = math.hypot(coord[j][0] - coord[i][0], coord[j][1] - coord[i][1])
            total += 0.5 * (stress.get(i, 0.0) + stress.get(j, 0.0)) * t * L
    return total if abs(total) > 1e-9 else None


def read_results_mat(source) -> dict:
    """Read a CUFSM **results** ``.mat`` (after you run the analysis in CUFSM)
    and extract the signature curve.  ``source`` is a path or the file bytes.

    Returns ``{half_wavelengths, signature, reference_load, n_lengths}`` where
    ``signature`` are the lowest-mode load factors per half-wavelength and
    ``reference_load`` is the applied axial load (load factor x this = buckling
    load), computed from the node stresses.  Feed the result to
    :func:`rack15512.cufsm.loads_from_signature` with ``reference=reference_load``
    to get ``Pcrl``/``Pcrd``."""
    sio = _require_scipy()
    mat = sio.loadmat(io.BytesIO(source) if isinstance(source, (bytes, bytearray))
                      else source)
    import numpy as np
    if "curve" not in mat or np.size(mat["curve"]) == 0:
        raise ValueError(
            "no analysis results ('curve') in this .mat - run the analysis in "
            "CUFSM and save the file, then load that results file here")
    hw, lf = _read_curve(mat["curve"])
    return {"half_wavelengths": hw, "signature": lf,
            "reference_load": _reference_load(mat), "n_lengths": len(hw)}
