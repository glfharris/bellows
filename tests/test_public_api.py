"""Tests for the public library import surface."""

from __future__ import annotations

import unittest

import bellows


class PublicApiTests(unittest.TestCase):
    def test_common_simulation_types_are_top_level_imports(self) -> None:
        self.assertIsNotNone(bellows.VentilationSimulation)
        self.assertIsNotNone(bellows.VentilatorSettings)
        self.assertIsNotNone(bellows.PatientMechanics)
        self.assertIsNotNone(bellows.LinearLung)
        self.assertIsNotNone(bellows.VenegasLung)
        self.assertIsNotNone(bellows.VenegasHysteresisLung)
        self.assertIsNotNone(bellows.SimulationRun)
        self.assertIsNotNone(bellows.SimulationRecorder)


if __name__ == "__main__":
    unittest.main()
