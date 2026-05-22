"""Tests for app display numerics."""

from __future__ import annotations

import unittest

from bellows.app import BellowsApp
from bellows.simulation.metrics import BreathSummary


class AppMetricsTests(unittest.TestCase):
    def test_monitor_numerics_use_simulation_breath_summary(self) -> None:
        app = BellowsApp()
        app.simulation.breath_history.append(_summary(0, 0.25, 0.75, 20.0, 5.0))

        text = app._numerics_renderable().plain

        self.assertIn("Ppeak   20 cmH2O", text)
        self.assertIn("VT  500 mL", text)
        self.assertIn("MV  6.0 L/min", text)
        self.assertIn("EtCO2  5.0 kPa", text)

    def test_monitor_numerics_include_recent_breath_delta(self) -> None:
        app = BellowsApp()
        app.simulation.breath_history.append(_summary(0, 0.25, 0.70, 22.0, 4.8))
        app.simulation.breath_history.append(_summary(1, 0.25, 0.75, 20.0, 5.0))

        text = app._numerics_renderable().plain

        self.assertEqual(text.count("\n"), 1)
        self.assertIn("Ppeak   20 (-2) cmH2O", text)
        self.assertIn("VT  500 (+50) mL", text)
        self.assertIn("MV  6.0 (+0.6) L/min", text)
        self.assertIn("EtCO2  5.0 (+0.2) kPa", text)

    def test_status_breath_context_uses_last_completed_breath(self) -> None:
        app = BellowsApp()
        app.simulation.breath_history.append(_summary(0, 0.25, 0.75, 20.0, 5.0))

        self.assertEqual(app._status_breath_context(), "last VT 500 mL  MV 6.0")


def _summary(
    breath: int,
    min_volume_l: float,
    max_volume_l: float,
    peak_pressure_cm_h2o: float,
    etco2_kpa: float,
) -> BreathSummary:
    return BreathSummary(
        breath=breath,
        start_time_s=breath * 5.0,
        end_time_s=(breath + 1) * 5.0,
        min_volume_l=min_volume_l,
        max_volume_l=max_volume_l,
        peak_pressure_cm_h2o=peak_pressure_cm_h2o,
        etco2_kpa=etco2_kpa,
    )


if __name__ == "__main__":
    unittest.main()
