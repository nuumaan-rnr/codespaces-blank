"""RSTAB-matching config options: EN1993 imperfection, connector override,
nonlinear axial-dependent base."""
import os, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from rack15512.builder import RackConfig, build_rack, LevelSpec
from rack15512.engine.opensees import OpenSeesEngine
from rack15512.model import Imperfection


def test_en1993_imperfection_is_flat_phi_s():
    imp = Imperfection(n_cols=4, phi_s=1/300, standard="EN1993", phi_min=1/500)
    assert abs(imp.value() - 1/300) < 1e-9          # flat, no 2x / sqrt factor
    imp15 = Imperfection(n_cols=4, phi_s=1/300, standard="EN15512", phi_l=0)
    assert imp15.value() > imp.value()              # EN 15512 is larger (amplified)


def test_en1993_alpha_hm_reduction_matches_rstab():
    # RSTAB "Calculate value of inclination" (EN 1993-1-1 5.3.2(3)):
    # Phi = Phi0 * alpha_h * alpha_m, with h = 7965 mm, m = 4 columns/row.
    m = build_rack(RackConfig(module="single", n_bays=3,
                              levels=[LevelSpec(gap=1800.0)], frame_height=7965.0,
                              imperfection_standard="EN1993",
                              imperfection_alpha_hm=True,
                              phi_s=1/200, phi_s_cross=1/300))
    imp = m.imperfection
    assert imp.n_cols == 4 and imp.alpha_hm and imp.height == 7965.0
    assert abs(imp._alpha_hm() - 0.5602) < 2e-3            # 0.709 * 0.791
    assert abs(1.0 / imp.value_for("+x") - 357.0) < 1.0    # DA: 1/200 -> 1/357
    assert abs(1.0 / imp.value_for("-x") - 357.0) < 1.0
    assert abs(1.0 / imp.value_for("+y") - 535.5) < 1.0    # CA: 1/300 -> 1/535
    # without alpha_hm the EN1993 path stays flat (no reduction, no phi_min lift)
    flat = Imperfection(n_cols=4, phi_s=1/200, standard="EN1993", phi_min=1/500)
    assert abs(flat.value() - 1/200) < 1e-9


def test_member_self_weight_in_dead_case():
    # RSTAB's LC1 has self-weight active (gamma=78.5 kN/m3); OpenSees applies no
    # gravity on its own, so the builder must add A*rho*g member self-weight to
    # the dead case as a global -Z UDL.  Default on; can be switched off.
    from rack15512.builder import _RHO_STEEL, _G_ACC
    m = build_rack(RackConfig(module="single", n_bays=2,
                              levels=[LevelSpec(gap=2000.0)], frame_height=2200.0))
    dead = m.load_cases["dead"]
    # one self-weight UDL per member (plus the dead_load_beam UDLs on the beams)
    sw = [ml for ml in dead.member_loads]
    assert len(sw) >= len(m.members)                  # every member got self-wt
    # an upright's self-weight UDL magnitude = A * rho * g
    up = next(mm for mm in m.members.values() if mm.member_set == "uprights")
    a = m.sections[up.section].A
    got = [abs(ml.qz) for ml in dead.member_loads if ml.member == up.id]
    assert any(abs(q - a * _RHO_STEEL * _G_ACC) < 1e-6 for q in got)
    # off -> no self-weight (only the beam dead UDLs remain)
    m0 = build_rack(RackConfig(module="single", n_bays=2,
                               levels=[LevelSpec(gap=2000.0)], frame_height=2200.0,
                               include_self_weight=False))
    assert len(m0.load_cases["dead"].member_loads) < len(m.members)


def test_calculated_beam_connector_stiffness():
    # 'calculated' beam stiffness = factor * E*I_b/L_b (beam_stiffness module),
    # like the base R899 option; an explicit override still wins.
    from rack15512.beam_stiffness import derived_connector_stiffness

    class _B:                                   # minimal beam section
        Iz = 800000.0
        material = "steel"
    assert abs(derived_connector_stiffness(_B(), 210000.0, 2700.0, 2.0)
               - 2.0 * 210000.0 * 800000.0 / 2700.0) < 1.0
    # factor scales linearly (6 = double-curvature/sway, the stiffest)
    k2 = derived_connector_stiffness(_B(), 210000.0, 2700.0, 2.0)
    k6 = derived_connector_stiffness(_B(), 210000.0, 2700.0, 6.0)
    assert abs(k6 / k2 - 3.0) < 1e-6

    base = dict(module="single", n_bays=2, bay_width=2700.0,
                levels=[LevelSpec(gap=2000.0)], frame_height=2200.0)
    mcalc = build_rack(RackConfig(**base, connector_stiffness_source="calculated",
                                  connector_calc_factor=6.0))
    mman = build_rack(RackConfig(**base, connector_stiffness_source="manual",
                                 connector_stiffness=42.0e6))
    bc = next(mm for mm in mcalc.members.values()
              if mm.member_set == "pallet beams")
    bm = next(mm for mm in mman.members.values()
              if mm.member_set == "pallet beams")
    assert bc.hinge_i.rz > bm.hinge_i.rz          # 6EI/L stiffer than 42 kNm/rad
    assert abs(bm.hinge_i.rz - 42.0e6) < 1.0      # manual value used verbatim


def test_stiffness_gamma_m_softens_design_stiffness():
    # E/gamma_M1 design stiffness (RSTAB "Materials (partial factor gamma_M)"):
    # at 1st order the sway scales as 1/E, so gamma_M=1.1 gives ~1.1x the sway.
    from rack15512.engine.opensees import OpenSeesEngine
    from rack15512.analysis import run_all
    base = dict(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                frame_height=2200.0)
    m0 = build_rack(RackConfig(**base, stiffness_gamma_m=1.0))
    m1 = build_rack(RackConfig(**base, stiffness_gamma_m=1.1))
    assert m1.analysis.stiffness_gamma_m == 1.1
    for mm in (m0, m1):
        mm.analysis.order = 1                      # linear: clean 1/E scaling

    def sway(model):
        for r in run_all(model):
            if r.converged and r.combo == "ULS1" and r.imp_direction == "+x":
                return max(abs(d[0]) for d in r.displacements.values())
        return 0.0
    s0, s1 = sway(m0), sway(m1)
    assert s0 > 0 and abs(s1 / s0 - 1.1) < 0.02     # ~10% softer


def test_connector_override_applied():
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, connector_stiffness_override=73.0e6))
    beams = [mm for mm in m.members.values() if mm.member_set == "pallet beams"]
    assert beams and all(b.hinge_i.rz == 73.0e6 and b.hinge_j.rz == 73.0e6 for b in beams)


def test_base_table_interp_and_tearing():
    tab = [[0, 1e3], [30, 2244e4], [80, 12381e4]]
    f = OpenSeesEngine._interp_base
    assert f(-5, tab) == 1e3                          # uplift -> tearing (C_MIN)
    assert f(100, tab) == 12381e4                     # flat beyond last point
    assert 2244e4 < f(55, tab) < 12381e4              # interpolates


def test_base_table_stored_on_model():
    tab = [[0, 1e3], [60, 8326e4]]
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, base_axial_table=tab))
    assert m.base_axial_table == tab


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))


def test_placement_accidental_on_interior_frame_by_default():
    """RSTAB/EN 15512 load the governing INTERIOR upright line (shared between two
    bays), not the corner/edge.  Default load_frame -> an interior line; an
    explicit 0 still pins the end frame; single-bay falls back to the end."""
    m = build_rack(RackConfig(module="single", n_bays=3, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0))
    xs = [nd.x for nd in m.nodes.values()]
    xmin, xmax = min(xs), max(xs)
    pl = m.nodes[m.load_cases["placement"].nodal_loads[0].node]
    ac = m.nodes[m.load_cases["accidental_x"].nodal_loads[0].node]
    assert xmin < pl.x < xmax              # interior, not an end/corner line
    assert xmin < ac.x < xmax

    # explicit end frame still honoured
    e = build_rack(RackConfig(module="single", n_bays=3, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, load_frame=0))
    assert e.nodes[e.load_cases["placement"].nodal_loads[0].node].x == min(
        nd.x for nd in e.nodes.values())

    # single bay: no interior line -> end frame
    s = build_rack(RackConfig(module="single", n_bays=1, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0))
    assert s.nodes[s.load_cases["placement"].nodal_loads[0].node].x == min(
        nd.x for nd in s.nodes.values())


def test_connector_looseness_modelled_or_lumped():
    # default: looseness recorded on the hinge but carried in phi_l (engine does
    # NOT model the dead-band)
    m0 = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                               frame_height=2200.0, connector_looseness=0.01))
    b0 = next(mm for mm in m0.members.values() if mm.member_set == "pallet beams")
    assert b0.hinge_i.looseness == 0.01                 # recorded
    assert m0.imperfection.phi_l >= 0.01                # carried in the imperfection
    assert m0.model_connector_looseness is False

    # modelled directly: engine models the dead-band, NOT lumped into phi_l
    m1 = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                               frame_height=2200.0, connector_looseness=0.01,
                               model_connector_looseness=True))
    b1 = next(mm for mm in m1.members.values() if mm.member_set == "pallet beams")
    assert b1.hinge_i.looseness == 0.01
    assert m1.imperfection.phi_l == 0.0
    assert m1.model_connector_looseness is True


def test_nonlinear_connector_moment_rotation():
    import os, tempfile
    from rack15512 import io_json
    mphi = [[0.01, 0.73e6], [0.04, 2.0e6], [0.10, 3.0e6]]
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, connector_moment_rotation=mphi))
    b = next(mm for mm in m.members.values() if mm.member_set == "pallet beams")
    assert b.hinge_i.m_phi_z == mphi and b.hinge_j.m_phi_z == mphi
    # io_json round-trips the diagram
    p = os.path.join(tempfile.mkdtemp(), "m.json")
    io_json.save(m, p)
    m2 = io_json.load(p)
    b2 = next(mm for mm in m2.members.values() if mm.member_set == "pallet beams")
    assert b2.hinge_i.m_phi_z == mphi


def test_plastic_connector_law():
    import os, tempfile
    from rack15512 import io_json
    m = build_rack(RackConfig(module="single", n_bays=2, levels=[LevelSpec(gap=2000.0)],
                              frame_height=2200.0, connector_plastic=True,
                              connector_m_rd=2.5e6, connector_hardening=0.03,
                              connector_phi_u=0.06))
    b = next(mm for mm in m.members.values() if mm.member_set == "pallet beams")
    assert b.hinge_i.plastic is True
    assert b.hinge_i.m_rd_z == 2.5e6
    assert b.hinge_i.hardening == 0.03 and b.hinge_i.phi_u == 0.06
    # round-trips
    p = os.path.join(tempfile.mkdtemp(), "m.json")
    io_json.save(m, p)
    b2 = next(mm for mm in io_json.load(p).members.values()
              if mm.member_set == "pallet beams")
    assert b2.hinge_i.plastic is True and b2.hinge_i.phi_u == 0.06


def test_rstab_behavior_defaults():
    """RSTAB-matching behaviors (validated on the Zepto model, <=2%):
    SLS combinations linear, stepped axial-dependent base from the master,
    EN1993 flat imperfection 1/300 DA / 1/200 CA, connector interpolation."""
    from rack15512.master_xlsx import load_master
    mw = load_master("examples/Master_Template_FINAL_mount_offset.xlsx")
    m = build_rack(RackConfig(master=mw, module="single", n_bays=2,
                              bay_width=2300.0, frame_height=2000.0,
                              levels=[LevelSpec(gap=1500.0,
                                                beam_section="RHS60X40X1.6",
                                                pallet_load=5000.0)],
                              upright_section="UP0010",
                              steel_E=200000.0, steel_G=76900.0))
    # SLS combos run geometrically linear (RSTAB), ULS at the model order
    assert all(c.order == 1 for c in m.combinations if c.kind == "SLS")
    assert all(c.order in (None, 2) for c in m.combinations if c.kind == "ULS")
    # base 'auto' -> stepped axial-dependent table from the master, tearing at 0
    assert m.base_axial_table is not None
    assert m.base_axial_table[0][0] == 0.0 and m.base_axial_table[1][0] == 30.0
    # EN1993 flat imperfection defaults
    assert m.imperfection.standard == "EN1993"
    assert abs(1 / m.imperfection.value_for("+x") - 300) < 1
    assert abs(1 / m.imperfection.value_for("+y") - 200) < 1
    # steel E/G override
    assert all(mat.E == 200000.0 and mat.G == 76900.0
               for mat in m.materials.values())
    # connector stiffness interpolates between tested upright thicknesses
    s = mw.library.get("RHS60X40X1.6")
    k16, k18, k20 = (s.connector_k_for(t) for t in (1.6, 1.8, 2.0))
    assert k16 < k18 < k20 and abs(k18 - (k16 + k20) / 2) < 1e3
    # order round-trips through json
    import os, tempfile
    from rack15512 import io_json
    p = os.path.join(tempfile.mkdtemp(), "m.json")
    io_json.save(m, p)
    m2 = io_json.load(p)
    assert all(c.order == 1 for c in m2.combinations if c.kind == "SLS")
