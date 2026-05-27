"""Directional tests for ventilator modes.

These are not unit tests of individual physics equations — they drive the
full simulation for a few breaths and assert qualitative behaviour
(higher Pinsp -> more volume, PRVC converges to the VT target, APRV
swings between two pressure levels at the configured timing).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.lung_model import LinearLung
from bellows.simulation.mechanics import apply_ventilator_intent
from bellows.simulation.phase import PHASE_EXPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import passive_expiration
from tests.helpers import per_breath_tidal, run_for_seconds


class VolumeControlTests(unittest.TestCase):
    def test_lower_compliance_raises_peak_pressure(self) -> None:
        soft = VentilationSimulation(
            patient=PatientMechanics(lung_model=LinearLung(compliance_l_per_cm_h2o=0.06))
        )
        stiff = VentilationSimulation(
            patient=PatientMechanics(lung_model=LinearLung(compliance_l_per_cm_h2o=0.03))
        )
        soft_samples = run_for_seconds(soft, 15.0)
        stiff_samples = run_for_seconds(stiff, 15.0)
        soft_peak = max(s.pressure_cm_h2o for s in soft_samples)
        stiff_peak = max(s.pressure_cm_h2o for s in stiff_samples)
        self.assertGreater(stiff_peak, soft_peak)

    def test_higher_vt_delivers_more_volume_and_pressure(self) -> None:
        low = VentilationSimulation(
            settings=VentilatorSettings(mode="VCV", vt_ml=300.0)
        )
        high = VentilationSimulation(
            settings=VentilatorSettings(mode="VCV", vt_ml=600.0)
        )
        low_samples = run_for_seconds(low, 15.0)
        high_samples = run_for_seconds(high, 15.0)
        # Delivered VT per breath (volume excursion) should track the setting.
        low_vt = max(per_breath_tidal(low_samples, "volume_ml").values())
        high_vt = max(per_breath_tidal(high_samples, "volume_ml").values())
        self.assertGreater(high_vt, low_vt * 1.5)
        # Pushing twice the volume against the same lung needs more pressure.
        low_peak = max(s.pressure_cm_h2o for s in low_samples)
        high_peak = max(s.pressure_cm_h2o for s in high_samples)
        self.assertGreater(high_peak, low_peak)

    def test_large_step_splits_at_inspiratory_boundary(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="VCV",
                rr_bpm=60.0,
                vt_ml=500.0,
                peep_cm_h2o=0.0,
                ie_i=1.0,
                ie_e=1.0,
            )
        )

        samples = sim.step_many(0.75)

        self.assertGreater(len(samples), 1)
        self.assertLessEqual(max(sample.volume_ml for sample in samples), 500.0)
        self.assertEqual(samples[-1].phase, PHASE_EXPIRATION)


class PressureControlTests(unittest.TestCase):
    def test_higher_pinsp_delivers_more_volume(self) -> None:
        low = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=10.0)
        )
        high = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=20.0)
        )
        low_samples = run_for_seconds(low, 15.0)
        high_samples = run_for_seconds(high, 15.0)
        low_vt = max(s.volume_ml for s in low_samples)
        high_vt = max(s.volume_ml for s in high_samples)
        self.assertGreater(high_vt, low_vt * 1.5)

    def test_higher_resistance_reduces_peak_flow_magnitudes(self) -> None:
        # In PCV, both inspiratory and expiratory flow are driven by the
        # pressure gradient through airway resistance. Doubling R should
        # reduce the peak |flow| reached during both phases.
        low_r = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=20.0),
            patient=PatientMechanics(resistance_cm_h2o_s_per_l=10.0),
        )
        high_r = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=20.0),
            patient=PatientMechanics(resistance_cm_h2o_s_per_l=25.0),
        )
        low_r_samples = run_for_seconds(low_r, 15.0)
        high_r_samples = run_for_seconds(high_r, 15.0)
        low_r_peak_insp = max(s.flow_l_min for s in low_r_samples)
        high_r_peak_insp = max(s.flow_l_min for s in high_r_samples)
        low_r_peak_exp = min(s.flow_l_min for s in low_r_samples)
        high_r_peak_exp = min(s.flow_l_min for s in high_r_samples)
        self.assertGreater(low_r_peak_insp, high_r_peak_insp)
        # Expiratory flow is negative; "more flow" means more negative.
        self.assertLess(low_r_peak_exp, high_r_peak_exp)

    def test_pressure_target_has_finite_rise_time(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="PCV",
                rr_bpm=10.0,
                peep_cm_h2o=5.0,
                pinsp_cm_h2o=20.0,
                pressure_rise_time_s=0.08,
            )
        )

        first = sim.step(0.01)
        samples = run_for_seconds(sim, 0.1)

        self.assertGreater(first.pressure_cm_h2o, 5.0)
        self.assertLess(first.pressure_cm_h2o, 25.0)
        self.assertGreater(samples[-1].pressure_cm_h2o, 23.0)
        self.assertLess(samples[-1].pressure_cm_h2o, 25.5)

    def test_pressure_is_stateful_across_expiratory_transition(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="PCV",
                rr_bpm=10.0,
                peep_cm_h2o=5.0,
                pinsp_cm_h2o=20.0,
                pressure_rise_time_s=0.08,
            )
        )

        samples = []
        for _ in range(260):
            samples.extend(sim.step_many(0.01))

        first_exp_index = next(
            index
            for index, sample in enumerate(samples)
            if sample.phase == PHASE_EXPIRATION
        )
        last_insp = samples[first_exp_index - 1]
        first_exp = samples[first_exp_index]

        self.assertGreater(first_exp.pressure_cm_h2o, sim.settings.peep_cm_h2o)
        self.assertLess(
            last_insp.pressure_cm_h2o - first_exp.pressure_cm_h2o,
            6.0,
        )


class PEEPTests(unittest.TestCase):
    def test_higher_peep_raises_baseline_pressure(self) -> None:
        # End-expiratory airway pressure should sit at PEEP (the ventilator
        # holds the floor there). Min pressure across a few stabilised breaths
        # should track the setting.
        def baseline(peep: float) -> float:
            sim = VentilationSimulation(
                settings=VentilatorSettings(mode="VCV", peep_cm_h2o=peep)
            )
            samples = run_for_seconds(sim, 20.0)
            # Drop the first breath while the lung settles onto PEEP.
            stable = [s for s in samples if s.breath >= 1]
            return min(s.pressure_cm_h2o for s in stable)

        low = baseline(5.0)
        high = baseline(10.0)
        self.assertAlmostEqual(low, 5.0, delta=0.5)
        self.assertAlmostEqual(high, 10.0, delta=0.5)
        self.assertGreater(high, low)


class ExpiratoryValveTests(unittest.TestCase):
    def test_valve_resistance_raises_airway_pressure_during_expiratory_flow(
        self,
    ) -> None:
        patient = PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.05),
            resistance_cm_h2o_s_per_l=10.0,
        )
        ideal_valve = apply_ventilator_intent(
            patient,
            passive_expiration(
                VentilatorSettings(expiratory_valve_resistance_cm_h2o_s_per_l=0.0),
            ),
            lung_volume_l=1.0,
            airway_pressure_cm_h2o=5.0,
            dt_s=0.01,
        )
        resistive_valve = apply_ventilator_intent(
            patient,
            passive_expiration(
                VentilatorSettings(expiratory_valve_resistance_cm_h2o_s_per_l=5.0),
            ),
            lung_volume_l=1.0,
            airway_pressure_cm_h2o=5.0,
            dt_s=0.01,
        )

        self.assertAlmostEqual(ideal_valve.pressure_cm_h2o, 5.0)
        self.assertGreater(resistive_valve.pressure_cm_h2o, 5.0)
        self.assertGreater(resistive_valve.flow_l_s, ideal_valve.flow_l_s)

    def test_reported_flow_matches_volume_change_when_volume_hits_zero(self) -> None:
        settings = VentilatorSettings(
            peep_cm_h2o=0.0,
            expiratory_valve_resistance_cm_h2o_s_per_l=0.0,
        )
        patient = PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.05),
            resistance_cm_h2o_s_per_l=1.0,
        )

        step = apply_ventilator_intent(
            patient,
            passive_expiration(settings),
            lung_volume_l=0.01,
            airway_pressure_cm_h2o=0.0,
            dt_s=1.0,
        )

        self.assertEqual(step.lung_volume_l, 0.0)
        self.assertAlmostEqual(step.flow_l_s, -0.01)


class PRVCTests(unittest.TestCase):
    def test_applied_pinsp_converges_to_target_vt(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="PRVC", vt_ml=400.0)
        )
        samples = run_for_seconds(sim, 45.0)
        tidal_per_breath = per_breath_tidal(samples, "volume_ml")
        last_few = [
            tidal_per_breath[b] for b in sorted(tidal_per_breath)[-3:]
        ]
        for vt_ml in last_few:
            self.assertAlmostEqual(vt_ml, 400.0, delta=25.0)

    def test_adapts_to_stiffer_lung(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="PRVC", vt_ml=400.0)
        )
        run_for_seconds(sim, 20.0)
        before = sim.modes["PRVC"].applied_pinsp_cm_h2o
        sim.patient = replace(
            sim.patient,
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.03),
        )
        run_for_seconds(sim, 25.0)
        after = sim.modes["PRVC"].applied_pinsp_cm_h2o
        self.assertGreater(after, before)


class APRVTests(unittest.TestCase):
    def test_pressure_swings_between_p_low_and_p_high(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="APRV",
                p_high_cm_h2o=22.0,
                p_low_cm_h2o=5.0,
                t_high_s=3.0,
                t_low_s=0.5,
            )
        )
        samples = run_for_seconds(sim, 12.0)
        pressures = [s.pressure_cm_h2o for s in samples]
        self.assertAlmostEqual(max(pressures), 22.0, delta=0.5)
        # Release brings pressure down close to p_low (decay isn't full in 0.5s
        # but it must be well below p_high)
        self.assertLess(min(pressures), 15.0)

    def test_cycle_length_uses_t_high_plus_t_low(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="APRV",
                t_high_s=4.0,
                t_low_s=0.6,
            )
        )
        run_for_seconds(sim, 30.0)
        # 30s / 4.6s per cycle ≈ 6.5 breaths
        self.assertGreaterEqual(sim.breath, 6)
        self.assertLessEqual(sim.breath, 7)


class ModeSwitchTests(unittest.TestCase):
    def test_pending_settings_apply_at_breath_boundary(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(mode="VCV"))
        run_for_seconds(sim, 2.0)
        sim.queue_settings(replace(sim.settings, mode="PCV"))
        # Should still be VCV until next breath boundary
        self.assertEqual(sim.settings.mode, "VCV")
        run_for_seconds(sim, 10.0)
        self.assertEqual(sim.settings.mode, "PCV")


class ModeMetadataTests(unittest.TestCase):
    def test_mode_control_keys_describe_ventilator_setting_rows(self) -> None:
        sim = VentilationSimulation()

        self.assertEqual(
            sim.mode_for("VCV").control_keys,
            ("target", "rr", "peep", "ie"),
        )
        self.assertEqual(
            sim.mode_for("PCV").control_keys,
            ("target", "rr", "peep", "ie"),
        )
        self.assertEqual(
            sim.mode_for("PRVC").control_keys,
            ("target", "rr", "peep", "ie"),
        )
        self.assertEqual(
            sim.mode_for("APRV").control_keys,
            ("p_high", "p_low", "t_high", "t_low"),
        )

    def test_modes_can_override_control_labels(self) -> None:
        sim = VentilationSimulation()

        self.assertEqual(sim.mode_for("VCV").control_label("target"), "VT target")
        self.assertEqual(sim.mode_for("PCV").control_label("target"), "Pinsp")
        self.assertEqual(sim.mode_for("PRVC").control_label("target"), "VT target")

    def test_mode_target_and_pending_summary_text_is_mode_owned(self) -> None:
        sim = VentilationSimulation()

        self.assertEqual(
            sim.mode_for("PCV").target_status(VentilatorSettings(mode="PCV")),
            "Pinsp 15 cmH2O",
        )
        self.assertEqual(
            sim.mode_for("VCV").pending_summary(VentilatorSettings(mode="VCV")),
            "RR 14  PEEP 5  I:E 1:2",
        )
        self.assertEqual(
            sim.mode_for("APRV").pending_summary(VentilatorSettings(mode="APRV")),
            "P_high 25  P_low 5  T_high 4.0  T_low 0.6",
        )


if __name__ == "__main__":
    unittest.main()
