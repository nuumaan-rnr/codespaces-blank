"""Section master library.

Reads a master file (CSV or JSON) holding ALL your sections with their full
3D properties, tagged by role (upright / beam / bracing / ...).  Members
are then assigned by section name - the library hands the complete,
solver-ready property set (A, Iy, Iz, J, Wely, Welz, effective values,
buckling curves) to the model.

Canonical CSV columns (header row required):

    name, role, A, Iy, Iz, J, Wely, Welz,
    A_eff, Wy_eff, Wz_eff, curve_y, curve_z, material, description

A_eff/Wy_eff/Wz_eff may be blank (gross values are used), curves default
to 'b', material defaults to 'steel'.  If your master uses different
column names, pass `mapping={'your column': 'canonical name', ...}`.

Optional extra columns (all blank-able): connector_k, connector_m_rd,
connector_looseness, Avy, Avz, It_gross, Iw_gross, y0.  Avy/Avz are shear
areas: when both are present the FEA builds a Timoshenko (shear-flexible)
beam for that section instead of an Euler-Bernoulli one.

Property axes follow the member local-axes convention documented in
`rack15512.model` (Iz = axis engaged by gravity bending of horizontal
beams and by down-aisle bending of uprights).
"""

from __future__ import annotations

import csv
import json
import os
from typing import Dict, List, Optional

from .model import CrossSection

_NUM_FIELDS = ("A", "Iy", "Iz", "J", "Wely", "Welz")
# optional columns; connector_* in N*mm units (per-beam connector data);
# Avy/Avz are shear areas (Timoshenko); It_gross/Iw_gross/y0 are the
# gross torsion / warping / shear-centre props for the FT-buckling check
_OPT_NUM_FIELDS = ("A_eff", "Wy_eff", "Wz_eff",
                   "connector_k", "connector_m_rd", "connector_looseness",
                   "Avy", "Avz", "It_gross", "Iw_gross", "y0")
_CURVES = ("a0", "a", "b", "c", "d")


class SectionLibrary:
    def __init__(self, sections: Optional[Dict[str, CrossSection]] = None):
        self.sections: Dict[str, CrossSection] = sections or {}
        # CUFSM data attached by section name (rack15512.cufsm.CufsmData);
        # build_rack applies it to every matching section automatically.
        self.cufsm: Dict[str, object] = {}

    def attach_cufsm(self, name: str, data: object) -> None:
        """Associate CUFSM data (a ``rack15512.cufsm.CufsmData``) with a section
        by name.  When that section is used in :func:`build_rack`, the gross
        torsion/warping/shear-centre (from the model) and the effective area +
        DSM data (from the signature) are populated automatically."""
        self.cufsm[name] = data

    # ------------------------------------------------------------- loading
    @classmethod
    def from_csv(cls, path: str,
                 mapping: Optional[Dict[str, str]] = None) -> "SectionLibrary":
        with open(path, newline="", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
        return cls._from_rows(rows, mapping, source=path)

    @classmethod
    def from_json(cls, path: str,
                  mapping: Optional[Dict[str, str]] = None) -> "SectionLibrary":
        with open(path, encoding="utf-8") as f:
            rows = json.load(f)
        if isinstance(rows, dict):
            rows = rows.get("sections", [])
        return cls._from_rows(rows, mapping, source=path)

    @classmethod
    def from_file(cls, path: str,
                  mapping: Optional[Dict[str, str]] = None) -> "SectionLibrary":
        if path.lower().endswith((".xlsx", ".xlsm")):
            from .master_xlsx import load_master
            return load_master(path).library
        if path.lower().endswith(".json"):
            return cls.from_json(path, mapping)
        return cls.from_csv(path, mapping)

    @classmethod
    def bundled(cls) -> "SectionLibrary":
        """The example master shipped with the package (generic values for
        demonstration - replace with your tested section data)."""
        here = os.path.dirname(__file__)
        return cls.from_csv(os.path.join(here, "data", "sections_master.csv"))

    @classmethod
    def _from_rows(cls, rows: List[dict],
                   mapping: Optional[Dict[str, str]],
                   source: str = "") -> "SectionLibrary":
        lib = cls()
        errors = []
        for k, raw in enumerate(rows):
            row = {(mapping or {}).get(key, key).strip(): v
                   for key, v in raw.items() if key is not None}
            try:
                lib.sections[row["name"].strip()] = _row_to_section(row)
            except (KeyError, ValueError, AttributeError) as e:
                errors.append(f"row {k + 1}: {e}")
        if errors:
            raise ValueError(
                f"Section master '{source}' has invalid rows:\n  "
                + "\n  ".join(errors))
        if not lib.sections:
            raise ValueError(f"Section master '{source}' contains no sections")
        return lib

    # -------------------------------------------------------------- access
    def get(self, name: str) -> CrossSection:
        try:
            return self.sections[name]
        except KeyError:
            raise KeyError(
                f"Section '{name}' not in master "
                f"(available: {', '.join(sorted(self.sections))})") from None

    def names(self, role: Optional[str] = None) -> List[str]:
        return sorted(s.name for s in self.sections.values()
                      if role is None or s.role.lower() == role.lower())

    def roles(self) -> List[str]:
        return sorted({s.role for s in self.sections.values() if s.role})

    def add_to_model(self, model, *names: str) -> None:
        """Copy the named sections (with full properties) into the model."""
        for name in names:
            model.sections[name] = self.get(name)


def _row_to_section(row: dict) -> CrossSection:
    def num(key, required=True):
        v = str(row.get(key, "") or "").strip()
        if not v:
            if required:
                raise ValueError(f"missing numeric field '{key}'")
            return None
        return float(v)

    name = row["name"].strip()
    if not name:
        raise ValueError("empty section name")
    kw = {k: num(k) for k in _NUM_FIELDS}
    kw.update({k: num(k, required=False) for k in _OPT_NUM_FIELDS})
    for col, attr in (("curve_y", "buckling_curve_y"),
                      ("curve_z", "buckling_curve_z")):
        v = str(row.get(col, "") or "").strip().lower() or "b"
        if v not in _CURVES:
            raise ValueError(f"{col}='{v}' not one of {_CURVES}")
        kw[attr] = v
    return CrossSection(
        name=name,
        material=str(row.get("material", "") or "steel").strip() or "steel",
        role=str(row.get("role", "") or "").strip(),
        description=str(row.get("description", "") or "").strip(),
        **kw)
