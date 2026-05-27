"""Tests for reusable simulation runners."""

from __future__ import annotations

import unittest

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.runner import run_samples
from bellows.simulation.state import VentilatorSettings


class SimulationRunnerTests(unittest.TestCase):
    def test_runs_until_requested_seconds(self) -> None:
        sim = VentilationSimulation()
        samples = run_samples(sim, seconds=1.0, dt_s=0.01)

        self.assertEqual(len(samples), 100)
        self.assertAlmostEqual(sim.time_s, 1.0)

    def test_runs_until_requested_breaths(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))
        samples = run_samples(sim, breaths=2, dt_s=0.01)

        self.assertTrue(samples)
        self.assertEqual(sim.breath, 2)

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

    def test_runner_includes_boundary_substep_samples(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(rr_bpm=60.0))

        samples = run_samples(sim, seconds=0.75, dt_s=0.75)

        self.assertGreater(len(samples), 1)
        self.assertAlmostEqual(sim.time_s, 0.75)


if __name__ == "__main__":
    unittest.main()
