"""Tests for simulation state, settings, and patient preset contracts."""

from __future__ import annotations

import unittest
from dataclasses import replace

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.lung_model import (
    LinearLung,
    VenegasHysteresisLung,
    VenegasLung,
)
from bellows.simulation.presets import (
    LINEAR_PRESETS,
    LUNG_MODELS,
    PATIENT_PRESETS,
    VENEGAS_HYSTERESIS_PRESETS,
    VENEGAS_PRESETS,
    presets_for,
)
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from tests.helpers import run_for_seconds


class VentilatorSettingsTests(unittest.TestCase):
    def test_vcv_cycle_uses_rr_and_ie_ratio(self) -> None:
        settings = VentilatorSettings(mode="VCV", rr_bpm=12.0, ie_i=1.0, ie_e=3.0)
        self.assertAlmostEqual(settings.cycle_s, 5.0)
        self.assertAlmostEqual(settings.inspiratory_time_s, 1.25)
        self.assertAlmostEqual(settings.expiratory_time_s, 3.75)

    def test_aprv_cycle_uses_high_and_low_times(self) -> None:
        settings = VentilatorSettings(
            mode="APRV",
            rr_bpm=30.0,
            ie_i=1.0,
            ie_e=1.0,
            t_high_s=4.0,
            t_low_s=0.5,
        )
        self.assertAlmostEqual(settings.cycle_s, 4.5)
        self.assertAlmostEqual(settings.inspiratory_time_s, 4.0)
        self.assertAlmostEqual(settings.expiratory_time_s, 0.5)

    def test_vt_helpers_convert_volume_and_flow(self) -> None:
        settings = VentilatorSettings(mode="VCV", rr_bpm=10.0, vt_ml=600.0)
        self.assertAlmostEqual(settings.vt_l, 0.6)
        self.assertAlmostEqual(settings.inspiratory_flow_l_s, 0.3)

    def test_rejects_non_physical_numeric_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "rr_bpm"):
            VentilatorSettings(rr_bpm=0.0)
        with self.assertRaisesRegex(ValueError, "ie_i and ie_e"):
            VentilatorSettings(ie_e=0.0)
        with self.assertRaisesRegex(ValueError, "p_high_cm_h2o"):
            VentilatorSettings(
                mode="APRV",
                p_high_cm_h2o=5.0,
                p_low_cm_h2o=5.0,
            )
        with self.assertRaisesRegex(ValueError, "expiratory_valve_resistance"):
            VentilatorSettings(expiratory_valve_resistance_cm_h2o_s_per_l=-1.0)
        with self.assertRaisesRegex(ValueError, "pressure_rise_time_s"):
            VentilatorSettings(pressure_rise_time_s=-0.01)


class PatientMechanicsTests(unittest.TestCase):
    def test_rejects_non_physical_numeric_mechanics(self) -> None:
        with self.assertRaisesRegex(ValueError, "resistance"):
            PatientMechanics(resistance_cm_h2o_s_per_l=0.0)
        with self.assertRaisesRegex(ValueError, "etco2"):
            PatientMechanics(etco2_kpa=-1.0)


class VentilationSimulationStateTests(unittest.TestCase):
    def test_reset_clears_time_pending_settings_and_returns_to_equilibrium(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(peep_cm_h2o=8.0))
        sim.queue_settings(replace(sim.settings, mode="PCV"))
        run_for_seconds(sim, 2.0)
        self.assertGreater(sim.time_s, 0.0)
        self.assertIsNotNone(sim.pending_settings)
        run_for_seconds(sim, 4.0)
        self.assertIsNotNone(sim.last_breath_summary)

        sim.reset()

        self.assertEqual(sim.time_s, 0.0)
        self.assertEqual(sim.breath_time_s, 0.0)
        self.assertEqual(sim.breath, 0)
        self.assertIsNone(sim.pending_settings)
        self.assertIsNone(sim.last_breath_summary)
        self.assertEqual(len(sim.breath_history), 0)
        self.assertAlmostEqual(sim.lung_volume_l, 0.4)
        self.assertAlmostEqual(sim.airway_pressure_cm_h2o, 8.0)

    def test_aprv_reset_uses_low_pressure_for_equilibrium(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="APRV",
                peep_cm_h2o=10.0,
                p_low_cm_h2o=2.0,
            )
        )
        run_for_seconds(sim, 1.0)

        sim.reset()

        self.assertAlmostEqual(sim.lung_volume_l, 0.1)
        self.assertAlmostEqual(sim.airway_pressure_cm_h2o, 2.0)

    def test_completed_breaths_are_stored_in_history(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=12.0))

        run_for_seconds(sim, 12.0)

        self.assertGreaterEqual(len(sim.breath_history), 2)
        summary = sim.last_breath_summary
        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.breath, 1)
        self.assertGreater(summary.vt_ml, 0.0)
        self.assertGreater(summary.peak_pressure_cm_h2o, 0.0)

    def test_unknown_mode_raises_clear_error(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(mode="NOPE"))
        with self.assertRaisesRegex(ValueError, "Unknown ventilator mode 'NOPE'"):
            sim.step(0.01)

    def test_step_many_returns_all_boundary_substeps(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        convenience_sim = VentilationSimulation(
            settings=VentilatorSettings(rr_bpm=60.0)
        )

        samples = sim.step_many(0.75)
        final_sample = convenience_sim.step(0.75)

        self.assertGreater(len(samples), 1)
        self.assertEqual(samples[-1].phase, final_sample.phase)
        self.assertAlmostEqual(samples[-1].time_s, final_sample.time_s)

    def test_patient_changes_take_effect_immediately(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="VCV", vt_ml=500.0),
            patient=PatientMechanics(lung_model=LinearLung(0.06)),
        )
        soft_peak = max(s.pressure_cm_h2o for s in run_for_seconds(sim, 5.0))
        sim.patient = replace(sim.patient, lung_model=LinearLung(0.025))
        stiff_peak = max(s.pressure_cm_h2o for s in run_for_seconds(sim, 5.0))
        self.assertGreater(stiff_peak, soft_peak)


class PatientPresetTests(unittest.TestCase):
    def test_model_names_have_matching_preset_lists(self) -> None:
        self.assertEqual(LUNG_MODELS, ("Linear", "Venegas", "Venegas+H"))
        self.assertIs(presets_for("Linear"), LINEAR_PRESETS)
        self.assertIs(presets_for("Venegas"), VENEGAS_PRESETS)
        self.assertIs(presets_for("Venegas+H"), VENEGAS_HYSTERESIS_PRESETS)

    def test_unknown_preset_model_falls_back_to_linear_presets(self) -> None:
        self.assertIs(presets_for("Unknown"), LINEAR_PRESETS)
        self.assertIs(PATIENT_PRESETS, LINEAR_PRESETS)

    def test_presets_use_matching_lung_model_implementations(self) -> None:
        self.assertTrue(
            all(isinstance(p.mechanics.lung_model, LinearLung) for p in LINEAR_PRESETS)
        )
        self.assertTrue(
            all(
                isinstance(p.mechanics.lung_model, VenegasLung)
                for p in VENEGAS_PRESETS
            )
        )
        self.assertTrue(
            all(
                isinstance(p.mechanics.lung_model, VenegasHysteresisLung)
                for p in VENEGAS_HYSTERESIS_PRESETS
            )
        )


if __name__ == "__main__":
    unittest.main()
