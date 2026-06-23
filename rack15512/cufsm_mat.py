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
           "recommend_lengths"]

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
