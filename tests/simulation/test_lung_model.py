"""Tests for the LungModel implementations."""

from __future__ import annotations

import unittest
from dataclasses import replace

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.lung_model import (
    LinearLung,
    VenegasHysteresisLung,
    VenegasLung,
)
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from tests.helpers import peak_pressure, run_for_seconds


class LinearLungTests(unittest.TestCase):
    def test_pressure_proportional_to_volume(self) -> None:
        lung = LinearLung(compliance_l_per_cm_h2o=0.05)
        self.assertAlmostEqual(lung.elastic_pressure(0.0, PHASE_INSPIRATION), 0.0)
        self.assertAlmostEqual(lung.elastic_pressure(0.5, PHASE_INSPIRATION), 10.0)
        self.assertAlmostEqual(lung.elastic_slope(0.5, PHASE_INSPIRATION), 20.0)

    def test_rejects_non_positive_compliance(self) -> None:
        with self.assertRaisesRegex(ValueError, "compliance"):
            LinearLung(compliance_l_per_cm_h2o=0.0)


class VenegasLungTests(unittest.TestCase):
    def test_equilibrium_volume_is_inverse_of_elastic_pressure(self) -> None:
        lung = VenegasLung()
        for pressure in (5.0, 10.0, 15.0, 20.0, 25.0):
            v_eq = lung.equilibrium_volume(pressure, PHASE_EXPIRATION)
            recovered = lung.elastic_pressure(v_eq, PHASE_EXPIRATION)
            self.assertAlmostEqual(recovered, pressure, places=2)

    def test_higher_peep_recruits_more_volume(self) -> None:
        lung = VenegasLung()
        v_at_5 = lung.equilibrium_volume(5.0, PHASE_EXPIRATION)
        v_at_10 = lung.equilibrium_volume(10.0, PHASE_EXPIRATION)
        v_at_15 = lung.equilibrium_volume(15.0, PHASE_EXPIRATION)
        self.assertLess(v_at_5, v_at_10)
        self.assertLess(v_at_10, v_at_15)

    def test_slope_minimum_near_inflection_volume(self) -> None:
        # The Venegas sigmoid has its highest local compliance (lowest slope)
        # around V = a + b/2.
        lung = VenegasLung(
            inflection_cm_h2o=18.0,
            slope_width_cm_h2o=5.0,
            recruitable_volume_l=1.2,
        )
        slope_low = lung.elastic_slope(0.1, PHASE_INSPIRATION)
        slope_mid = lung.elastic_slope(0.55, PHASE_INSPIRATION)
        slope_high = lung.elastic_slope(1.0, PHASE_INSPIRATION)
        self.assertLess(slope_mid, slope_low)
        self.assertLess(slope_mid, slope_high)

    def test_pressure_keeps_rising_beyond_recruitable_volume(self) -> None:
        lung = VenegasLung(recruitable_volume_l=1.2)

        near_capacity = lung.elastic_pressure(1.2, PHASE_INSPIRATION)
        over_capacity = lung.elastic_pressure(1.4, PHASE_INSPIRATION)

        self.assertGreater(over_capacity, near_capacity)

    def test_rejects_non_physical_shape_parameters(self) -> None:
        with self.assertRaisesRegex(ValueError, "slope_width"):
            VenegasLung(slope_width_cm_h2o=0.0)
        with self.assertRaisesRegex(ValueError, "recruitable_volume"):
            VenegasLung(recruitable_volume_l=0.0)
        with self.assertRaisesRegex(ValueError, "residual_volume"):
            VenegasLung(residual_volume_l=-0.1)


class VenegasHysteresisTests(unittest.TestCase):
    def test_inspiratory_pressure_higher_than_expiratory(self) -> None:
        lung = VenegasHysteresisLung(hysteresis_offset_cm_h2o=4.0)
        for v in (0.1, 0.3, 0.5, 0.8, 1.0):
            self.assertGreater(
                lung.elastic_pressure(v, PHASE_INSPIRATION),
                lung.elastic_pressure(v, PHASE_EXPIRATION),
            )

    def test_offset_matches_setting(self) -> None:
        lung = VenegasHysteresisLung(hysteresis_offset_cm_h2o=4.0)
        diff = lung.elastic_pressure(0.5, PHASE_INSPIRATION) - lung.elastic_pressure(
            0.5, PHASE_EXPIRATION
        )
        self.assertAlmostEqual(diff, 4.0, places=3)

    def test_rejects_negative_hysteresis_offset(self) -> None:
        with self.assertRaisesRegex(ValueError, "hysteresis_offset"):
            VenegasHysteresisLung(hysteresis_offset_cm_h2o=-1.0)


class SimulationIntegrationTests(unittest.TestCase):
    def test_vcv_pressure_higher_with_venegas_than_linear(self) -> None:
        # At a low VT we're well below the Venegas inflection where compliance
        # is poor — VCV pushing 500 mL needs more pressure than against a
        # linear lung with the same overall compliance scale.
        common = VentilatorSettings(mode="VCV", vt_ml=500.0)
        linear_peak = peak_pressure(
            VentilationSimulation(
                settings=common,
                patient=PatientMechanics(lung_model=LinearLung(0.05)),
            )
        )
        venegas_peak = peak_pressure(
            VentilationSimulation(
                settings=common,
                patient=PatientMechanics(lung_model=VenegasLung()),
            )
        )
        self.assertGreater(venegas_peak, linear_peak)

    def test_prvc_pinsp_drops_with_recruitment(self) -> None:
        """Raising PEEP into the recruitable range should let PRVC drop its
        driving pressure for the same VT — the whole point of the
        non-linear lung models."""
        def converged_pinsp(peep: float) -> float:
            sim = VentilationSimulation(
                settings=VentilatorSettings(
                    mode="PRVC", vt_ml=500.0, peep_cm_h2o=peep
                ),
                patient=PatientMechanics(
                    lung_model=VenegasLung(
                        inflection_cm_h2o=18.0,
                        slope_width_cm_h2o=4.0,
                        recruitable_volume_l=1.2,
                    ),
                ),
            )
            run_for_seconds(sim, 90.0)
            return sim.modes["PRVC"].applied_pinsp_cm_h2o

        low_peep = converged_pinsp(5.0)
        better_peep = converged_pinsp(10.0)
        self.assertLess(better_peep, low_peep)

    def test_switching_lung_model_mid_simulation_keeps_running(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="VCV"),
            patient=PatientMechanics(lung_model=LinearLung(0.05)),
        )
        run_for_seconds(sim, 5.0)
        sim.patient = replace(sim.patient, lung_model=VenegasLung())
        run_for_seconds(sim, 10.0)
        sim.patient = replace(sim.patient, lung_model=VenegasHysteresisLung())
        final = run_for_seconds(sim, 10.0)
        self.assertTrue(final)


if __name__ == "__main__":
    unittest.main()
