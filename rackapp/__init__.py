"""rackapp - Storage rack structural analysis & EN 15512 design checks.

Pipeline:
    config (YAML) -> RackModel (nodes/members/hinges/supports)
                  -> load cases / imperfections / combinations
                  -> FEA engine (RFEM 6 or built-in 2nd-order solver)
                  -> results -> EN 15512 checks -> report / plots.
"""

__version__ = "0.1.0"
