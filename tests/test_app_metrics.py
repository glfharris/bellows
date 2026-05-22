"""Tests for app-owned display metrics."""

from __future__ import annotations

import unittest

from bellows.app import BellowsApp
from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.state import SimulationSample


class AppMetricsTests(unittest.TestCase):
    def test_minute_volume_uses_observed_breath_duration(self) -> None:
        app = BellowsApp()

        app._record_metrics(
            SimulationSample(
                time_s=0.0,
                pressure_cm_h2o=5.0,
                flow_l_min=0.0,
                volume_ml=250.0,
                co2_kpa=0.0,
                phase=PHASE_INSPIRATION,
                breath=0,
            )
        )
        app._record_metrics(
            SimulationSample(
                time_s=1.0,
                pressure_cm_h2o=20.0,
                flow_l_min=0.0,
                volume_ml=750.0,
                co2_kpa=5.0,
                phase=PHASE_EXPIRATION,
                breath=0,
            )
        )
        app._record_metrics(
            SimulationSample(
                time_s=5.0,
                pressure_cm_h2o=5.0,
                flow_l_min=0.0,
                volume_ml=250.0,
                co2_kpa=0.0,
                phase=PHASE_INSPIRATION,
                breath=1,
            )
        )

        self.assertEqual(app.metrics.completed_vt_ml, 500.0)
        self.assertEqual(app.metrics.completed_peak_pressure_cm_h2o, 20.0)
        self.assertEqual(app.metrics.completed_etco2_kpa, 5.0)
        self.assertAlmostEqual(app.metrics.completed_minute_volume_l_min, 6.0)


if __name__ == "__main__":
    unittest.main()
