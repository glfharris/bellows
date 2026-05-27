"""Tests for CLI-facing simulation configuration."""

from __future__ import annotations

import unittest

from bellows.config import build_simulation_config, parse_ie_ratio
from bellows.simulation.lung_model import VenegasLung


class SimulationConfigTests(unittest.TestCase):
    def test_builds_settings_from_startup_options(self) -> None:
        config = build_simulation_config(
            mode="prvc",
            vt_ml=450.0,
            rr_bpm=16.0,
            peep_cm_h2o=8.0,
            expiratory_valve_resistance_cm_h2o_s_per_l=4.0,
            pressure_rise_time_s=0.06,
            ie="1:3",
        )

        self.assertEqual(config.settings.mode, "PRVC")
        self.assertEqual(config.settings.vt_ml, 450.0)
        self.assertEqual(config.settings.rr_bpm, 16.0)
        self.assertEqual(config.settings.peep_cm_h2o, 8.0)
        self.assertEqual(
            config.settings.expiratory_valve_resistance_cm_h2o_s_per_l,
            4.0,
        )
        self.assertEqual(config.settings.pressure_rise_time_s, 0.06)
        self.assertEqual(config.settings.ie_i, 1.0)
        self.assertEqual(config.settings.ie_e, 3.0)

    def test_selects_preset_for_requested_lung_model(self) -> None:
        config = build_simulation_config(
            lung_model="Venegas",
            preset="Recruitable ARDS",
        )

        self.assertEqual(config.patient_preset_name, "Recruitable ARDS")
        self.assertIsInstance(config.patient.lung_model, VenegasLung)

    def test_rejects_unknown_mode(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown ventilator mode"):
            build_simulation_config(mode="NOPE")

    def test_rejects_unknown_preset_for_lung_model(self) -> None:
        with self.assertRaisesRegex(ValueError, "Unknown preset"):
            build_simulation_config(lung_model="Venegas", preset="Severe obstruction")

    def test_rejects_invalid_startup_settings(self) -> None:
        with self.assertRaisesRegex(ValueError, "rr_bpm"):
            build_simulation_config(rr_bpm=0.0)
        with self.assertRaisesRegex(ValueError, "p_high_cm_h2o"):
            build_simulation_config(p_low_cm_h2o=30.0)
        with self.assertRaisesRegex(ValueError, "expiratory_valve_resistance"):
            build_simulation_config(expiratory_valve_resistance_cm_h2o_s_per_l=-1.0)
        with self.assertRaisesRegex(ValueError, "pressure_rise_time_s"):
            build_simulation_config(pressure_rise_time_s=-0.01)

    def test_parse_ie_ratio_requires_two_positive_numbers(self) -> None:
        self.assertEqual(parse_ie_ratio("1:2"), (1.0, 2.0))

        with self.assertRaisesRegex(ValueError, "form I:E"):
            parse_ie_ratio("2")
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            parse_ie_ratio("1:0")


if __name__ == "__main__":
    unittest.main()
