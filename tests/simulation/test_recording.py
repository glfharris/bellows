"""Tests for collected simulation runs and recorders."""

from __future__ import annotations

import unittest

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.recording import SimulationRecorder, SimulationRun
from bellows.simulation.state import VentilatorSettings


class SimulationRunTests(unittest.TestCase):
    def test_run_behaves_like_a_sample_sequence(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        run = sim.run(breaths=2, dt_s=0.01)

        self.assertGreater(len(run), 0)
        self.assertIs(run[0], run.samples[0])
        self.assertEqual(list(run), list(run.samples))
        self.assertIsInstance(run[:2], SimulationRun)

    def test_columns_return_sample_attributes(self) -> None:
        sim = VentilationSimulation()
        run = sim.run(seconds=0.05, dt_s=0.01)

        self.assertEqual(run.column("time_s"), [sample.time_s for sample in run])
        self.assertEqual(
            run.columns("time_s", "pressure_cm_h2o"),
            {
                "time_s": [sample.time_s for sample in run],
                "pressure_cm_h2o": [sample.pressure_cm_h2o for sample in run],
            },
        )

    def test_breath_filters_by_breath_number_or_negative_index(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        run = sim.run(breaths=3, dt_s=0.01)

        first_breath = run.breath(0)
        last_breath = run.breath(-1)

        self.assertTrue(first_breath)
        self.assertTrue(last_breath)
        self.assertTrue(all(sample.breath == 0 for sample in first_breath))
        self.assertTrue(all(sample.breath == 2 for sample in last_breath))

    def test_last_completed_breath_uses_breath_summaries(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        run = sim.run(breaths=2, dt_s=0.01)

        last_completed = run.last_completed_breath()

        self.assertTrue(last_completed)
        self.assertIs(run.last_breath_summary, run.breath_summaries[-1])
        self.assertIs(run.breath_summary(-1), run.breath_summaries[-1])
        self.assertIs(run.breath_summary(1), run.breath_summaries[-1])
        self.assertEqual(last_completed.breath_summaries[-1].breath, 1)
        self.assertTrue(all(sample.breath == 1 for sample in last_completed))

    def test_summary_columns_return_breath_summary_attributes(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        run = sim.run(breaths=2, dt_s=0.01)

        self.assertEqual(
            run.summary_column("vt_ml"),
            [summary.vt_ml for summary in run.breath_summaries],
        )
        self.assertEqual(
            run.summary_columns("breath", "peak_pressure_cm_h2o"),
            {
                "breath": [summary.breath for summary in run.breath_summaries],
                "peak_pressure_cm_h2o": [
                    summary.peak_pressure_cm_h2o
                    for summary in run.breath_summaries
                ],
            },
        )

    def test_recorder_builds_a_run(self) -> None:
        sim = VentilationSimulation()
        recorder = SimulationRecorder(maxlen=2)

        recorded = recorder.record(sim.step_many(0.03))
        run = recorder.to_run()

        self.assertTrue(recorded)
        self.assertIsInstance(run, SimulationRun)
        self.assertLessEqual(len(run), 2)


if __name__ == "__main__":
    unittest.main()
