"""Tests for reusable simulation runners."""

from __future__ import annotations

import unittest

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.metrics import BreathHistory
from bellows.simulation.recording import SimulationRun
from bellows.simulation.runner import run_samples
from bellows.simulation.state import VentilatorSettings


class SimulationRunnerTests(unittest.TestCase):
    def test_runs_until_requested_seconds(self) -> None:
        sim = VentilationSimulation()
        initial = sim.current_sample()
        samples = run_samples(sim, seconds=1.0, dt_s=0.01)

        self.assertEqual(len(samples), 101)
        self.assertEqual(samples[0], initial)
        self.assertAlmostEqual(sim.time_s, 1.0)

    def test_runs_until_requested_breaths(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        samples = run_samples(sim, breaths=2, dt_s=0.01)

        self.assertTrue(samples)
        self.assertEqual(sim.breath, 2)

    def test_simulation_run_is_a_convenience_runner(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        run = sim.run(breaths=2, dt_s=0.01)

        self.assertIsInstance(run, SimulationRun)
        self.assertTrue(run)
        self.assertEqual(sim.breath, 2)
        self.assertEqual(len(run.breath_summaries), 2)

    def test_run_keeps_summaries_evicted_from_rolling_history(self) -> None:
        for maxlen in (0, 2):
            with self.subTest(maxlen=maxlen):
                sim = VentilationSimulation(
                    settings=VentilatorSettings(rr_bpm=60.0),
                    breath_history=BreathHistory(maxlen=maxlen),
                )

                # A single step may complete more breaths than history can retain.
                run = sim.run(seconds=5.0, dt_s=3.0)

                self.assertEqual(run.summary_column("breath"), list(range(5)))
                self.assertEqual(len(sim.breath_history), maxlen)

    def test_run_only_collects_summaries_completed_during_that_run(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(rr_bpm=60.0),
            breath_history=BreathHistory(maxlen=2),
        )
        sim.run(breaths=2)

        run = sim.run(breaths=1)

        self.assertEqual(run.summary_column("breath"), [2])
        self.assertEqual([s.breath for s in sim.breath_history], [1, 2])

    def test_run_includes_initial_state_sample_by_default(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", peep_cm_h2o=6.0)
        )
        initial = sim.current_sample()

        run = sim.run(seconds=0.01, dt_s=0.01)

        self.assertGreaterEqual(len(run), 2)
        self.assertEqual(run[0], initial)
        self.assertEqual(run[0].time_s, 0.0)
        self.assertEqual(run[1].time_s, 0.01)
        self.assertEqual(run[0].pressure_cm_h2o, 6.0)

    def test_run_can_skip_initial_state_sample(self) -> None:
        sim = VentilationSimulation()

        run = sim.run(seconds=0.01, dt_s=0.01, include_initial=False)

        self.assertEqual(len(run), 1)

    def test_seconds_are_relative_to_current_simulation_time(self) -> None:
        sim = VentilationSimulation()
        run_samples(sim, seconds=1.0, dt_s=0.01)
        samples = run_samples(sim, seconds=1.0, dt_s=0.01)

        self.assertGreaterEqual(len(samples), 100)
        self.assertAlmostEqual(sim.time_s, 2.0)

    def test_rejects_invalid_runner_values(self) -> None:
        sim = VentilationSimulation()
        with self.assertRaisesRegex(ValueError, "dt_s"):
            run_samples(sim, seconds=1.0, dt_s=0.0)
        with self.assertRaisesRegex(ValueError, "seconds"):
            run_samples(sim, seconds=-1.0)
        with self.assertRaisesRegex(ValueError, "breaths"):
            run_samples(sim, breaths=-1)

    def test_rejects_nonfinite_runner_values(self) -> None:
        for value in (float("nan"), float("inf"), -float("inf")):
            for name in ("dt_s", "seconds"):
                with self.subTest(name=name, value=value):
                    sim = VentilationSimulation()
                    with self.assertRaisesRegex(ValueError, name):
                        sim.run(**{name: value})
                    self.assertEqual(sim.time_s, 0.0)

    def test_runner_includes_boundary_substep_samples(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))

        samples = run_samples(sim, seconds=0.75, dt_s=0.75)

        self.assertGreater(len(samples), 1)
        self.assertAlmostEqual(sim.time_s, 0.75)


if __name__ == "__main__":
    unittest.main()
