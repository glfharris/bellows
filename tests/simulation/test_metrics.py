"""Tests for breath summaries and history."""

from __future__ import annotations

import unittest

from bellows.simulation.metrics import BreathAccumulator, BreathHistory, BreathSummary
from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.state import SimulationSample


class BreathAccumulatorTests(unittest.TestCase):
    def test_finishes_summary_for_observed_breath(self) -> None:
        accumulator = BreathAccumulator()

        accumulator.observe(
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
        accumulator.observe(
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
        summary = accumulator.finish(end_time_s=5.0)

        self.assertIsNotNone(summary)
        assert summary is not None
        self.assertEqual(summary.breath, 0)
        self.assertEqual(summary.vt_ml, 500.0)
        self.assertEqual(summary.peak_pressure_cm_h2o, 20.0)
        self.assertEqual(summary.etco2_kpa, 5.0)
        self.assertAlmostEqual(summary.minute_volume_l_min, 6.0)
        self.assertIsNone(accumulator.current_breath)

    def test_finish_without_samples_returns_none(self) -> None:
        accumulator = BreathAccumulator()

        self.assertIsNone(accumulator.finish(end_time_s=5.0))


class BreathHistoryTests(unittest.TestCase):
    def test_retains_bounded_recent_breaths(self) -> None:
        history = BreathHistory(maxlen=2)
        first = _summary(0, 0.0, 5.0)
        second = _summary(1, 5.0, 10.0)
        third = _summary(2, 10.0, 15.0)

        history.append(first)
        history.append(second)
        history.append(third)

        self.assertEqual(len(history), 2)
        self.assertIs(history.last, third)
        self.assertEqual(history.recent(1), [third])
        self.assertEqual(list(history), [second, third])

    def test_since_returns_breaths_completed_after_time(self) -> None:
        history = BreathHistory()
        early = _summary(0, 0.0, 5.0)
        late = _summary(1, 5.0, 10.0)
        history.append(early)
        history.append(late)

        self.assertEqual(history.since(7.0), [late])

    def test_clear_removes_breaths(self) -> None:
        history = BreathHistory()
        history.append(_summary(0, 0.0, 5.0))

        history.clear()

        self.assertEqual(len(history), 0)
        self.assertIsNone(history.last)


def _summary(breath: int, start_time_s: float, end_time_s: float) -> BreathSummary:
    return BreathSummary(
        breath=breath,
        start_time_s=start_time_s,
        end_time_s=end_time_s,
        min_volume_l=0.25,
        max_volume_l=0.75,
        peak_pressure_cm_h2o=20.0,
        etco2_kpa=5.0,
    )


if __name__ == "__main__":
    unittest.main()
