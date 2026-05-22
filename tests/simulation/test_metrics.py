"""Tests for breath metric aggregation."""

from __future__ import annotations

import unittest

from bellows.simulation.metrics import BreathMetricsTracker
from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.state import SimulationSample


class BreathMetricsTrackerTests(unittest.TestCase):
    def test_emits_summary_when_new_breath_starts(self) -> None:
        tracker = BreathMetricsTracker()

        self.assertIsNone(
            tracker.observe(
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
        )
        self.assertIsNone(
            tracker.observe(
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
        )
        summary = tracker.observe(
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

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.breath, 0)
        self.assertEqual(summary.vt_ml, 500.0)
        self.assertEqual(summary.peak_pressure_cm_h2o, 20.0)
        self.assertEqual(summary.etco2_kpa, 5.0)
        self.assertAlmostEqual(summary.minute_volume_l_min, 6.0)


if __name__ == "__main__":
    unittest.main()
