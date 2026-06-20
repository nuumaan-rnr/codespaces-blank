"""Worked CUFSM + Direct Strength Method check of a perforated rack upright.

Run:  python examples/cufsm_upright.py

Reads a CUFSM signature curve (examples/cufsm_upright_signature.csv), extracts
the local and distortional elastic buckling loads, takes the global elastic
load from the panel Euler load (in a full model this comes from the frame
analysis), and computes the DSM axial strength of the perforated upright -
including the members-with-holes net-section provisions.  No OpenSees model is
needed for this section-level check.
"""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from rack15512 import cufsm, dsm
from rack15512.model import CrossSection, Steel

HERE = os.path.dirname(__file__)

# a representative cold-formed perforated upright (S450GD, common for racks)
steel = Steel("S450GD", fy=450.0)
upright = CrossSection(name="UP-100x90x2.0 (perforated)", material="S450GD",
                       A=600.0, Iy=1.05e6, Iz=0.62e6, J=8.0e2,
                       Wely=2.1e4, Welz=1.4e4, role="upright")
Anet = 540.0                     # net area through a perforation (10% loss)

# 1) CUFSM signature curve -> local & distortional elastic buckling loads
hw, val = cufsm.read_signature_csv(
    os.path.join(HERE, "cufsm_upright_signature.csv"))
loads = cufsm.loads_from_signature(hw, val)          # values already in N
print(f"CUFSM local        Pcrl = {loads.Pcrl/1e3:7.1f} kN "
      f"(half-wavelength {loads.half_wavelength_local:.0f} mm)")
print(f"CUFSM distortional Pcrd = {loads.Pcrd/1e3:7.1f} kN "
      f"(half-wavelength {loads.half_wavelength_dist:.0f} mm)")

# 2) global elastic load: stand-alone, use the Euler load of the panel between
#    beam levels.  In a full run, take Pcre from the frame analysis instead.
L = 1500.0
Pcre = math.pi ** 2 * steel.E * min(upright.Iy, upright.Iz) / L ** 2
print(f"global (Euler, L={L:.0f} mm)  Pcre = {Pcre/1e3:7.1f} kN")

# 3) DSM nominal axial strength (members with holes)
Py = upright.A * steel.fy
col = dsm.column_strength(Py, Pcre, loads.Pcrl, loads.Pcrd,
                          Pynet=Anet * steel.fy)
gM1 = 1.1
print(f"\nPy = Ag*fy   = {Py/1e3:7.1f} kN")
print(f"Pynet=Anet*fy= {Anet*steel.fy/1e3:7.1f} kN")
print(f"Pne (global)        = {col.Pne/1e3:7.1f} kN")
print(f"Pnl (local)         = {col.Pnl/1e3:7.1f} kN")
print(f"Pnd (distortional)  = {col.Pnd/1e3:7.1f} kN")
print(f"Pn = min            = {col.Pn/1e3:7.1f} kN  ({col.governs} governs)")
print(f"Nb,Rd = Pn / gM1    = {col.Pn/gM1/1e3:7.1f} kN  (gM1 = {gM1})")

# 4) effective area for the EN 15512 effective-section (STRESS / BUCKLING) checks
A_eff = cufsm.effective_area(upright, steel, loads, Anet=Anet)
print(f"\nDSM effective area A_eff = {A_eff:6.0f} mm^2  "
      f"(gross {upright.A:.0f} mm^2)")
