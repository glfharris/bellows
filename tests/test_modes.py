"""Directional tests for ventilator modes.

These are not unit tests of individual physics equations — they drive the
full simulation for a few breaths and assert qualitative behaviour
(higher Pinsp -> more volume, PRVC converges to the VT target, APRV
swings between two pressure levels at the configured timing).
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.lung_model import LinearLung
from bellows.simulation.state import PatientMechanics, VentilatorSettings


def _run_for_seconds(sim: VentilationSimulation, seconds: float, dt_s: float = 0.01):
    samples = []
    for _ in range(int(seconds / dt_s)):
        samples.append(sim.step(dt_s))
    return samples


def _per_breath_max(samples, attr):
    by_breath: dict[int, float] = {}
    for s in samples:
        value = getattr(s, attr)
        by_breath[s.breath] = max(by_breath.get(s.breath, value), value)
    return by_breath


def _per_breath_tidal(samples, attr):
    """Per-breath (max - min) of an attribute. Useful for VT."""
    mins: dict[int, float] = {}
    maxs: dict[int, float] = {}
    for s in samples:
        value = getattr(s, attr)
        mins[s.breath] = min(mins.get(s.breath, value), value)
        maxs[s.breath] = max(maxs.get(s.breath, value), value)
    return {b: maxs[b] - mins[b] for b in mins}


class VolumeControlTests(unittest.TestCase):
    def test_lower_compliance_raises_peak_pressure(self) -> None:
        soft = VentilationSimulation(
            patient=PatientMechanics(lung_model=LinearLung(compliance_l_per_cm_h2o=0.06))
        )
        stiff = VentilationSimulation(
            patient=PatientMechanics(lung_model=LinearLung(compliance_l_per_cm_h2o=0.03))
        )
        soft_samples = _run_for_seconds(soft, 15.0)
        stiff_samples = _run_for_seconds(stiff, 15.0)
        soft_peak = max(s.pressure_cm_h2o for s in soft_samples)
        stiff_peak = max(s.pressure_cm_h2o for s in stiff_samples)
        self.assertGreater(stiff_peak, soft_peak)


class PressureControlTests(unittest.TestCase):
    def test_higher_pinsp_delivers_more_volume(self) -> None:
        low = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=10.0)
        )
        high = VentilationSimulation(
            settings=VentilatorSettings(mode="PCV", pinsp_cm_h2o=20.0)
        )
        low_samples = _run_for_seconds(low, 15.0)
        high_samples = _run_for_seconds(high, 15.0)
        low_vt = max(s.volume_ml for s in low_samples)
        high_vt = max(s.volume_ml for s in high_samples)
        self.assertGreater(high_vt, low_vt * 1.5)


class PRVCTests(unittest.TestCase):
    def test_applied_pinsp_converges_to_target_vt(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="PRVC", vt_ml=400.0)
        )
        samples = _run_for_seconds(sim, 45.0)
        tidal_per_breath = _per_breath_tidal(samples, "volume_ml")
        last_few = [
            tidal_per_breath[b] for b in sorted(tidal_per_breath)[-3:]
        ]
        for vt_ml in last_few:
            self.assertAlmostEqual(vt_ml, 400.0, delta=25.0)

    def test_adapts_to_stiffer_lung(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(mode="PRVC", vt_ml=400.0)
        )
        _run_for_seconds(sim, 20.0)
        before = sim.modes["PRVC"].applied_pinsp_cm_h2o
        sim.patient = replace(sim.patient, lung_model=LinearLung(compliance_l_per_cm_h2o=0.03))
        _run_for_seconds(sim, 25.0)
        after = sim.modes["PRVC"].applied_pinsp_cm_h2o
        self.assertGreater(after, before)


class APRVTests(unittest.TestCase):
    def test_pressure_swings_between_p_low_and_p_high(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="APRV",
                p_high_cm_h2o=22.0,
                p_low_cm_h2o=5.0,
                t_high_s=3.0,
                t_low_s=0.5,
            )
        )
        samples = _run_for_seconds(sim, 12.0)
        pressures = [s.pressure_cm_h2o for s in samples]
        self.assertAlmostEqual(max(pressures), 22.0, delta=0.5)
        # Release brings pressure down close to p_low (decay isn't full in 0.5s
        # but it must be well below p_high)
        self.assertLess(min(pressures), 15.0)

    def test_cycle_length_uses_t_high_plus_t_low(self) -> None:
        sim = VentilationSimulation(
            settings=VentilatorSettings(
                mode="APRV",
                t_high_s=4.0,
                t_low_s=0.6,
            )
        )
        _run_for_seconds(sim, 30.0)
        # 30s / 4.6s per cycle ≈ 6.5 breaths
        self.assertGreaterEqual(sim.breath, 6)
        self.assertLessEqual(sim.breath, 7)


class ModeSwitchTests(unittest.TestCase):
    def test_pending_settings_apply_at_breath_boundary(self) -> None:
        sim = VentilationSimulation(settings=VentilatorSettings(mode="VCV"))
        _run_for_seconds(sim, 2.0)
        sim.queue_settings(replace(sim.settings, mode="PCV"))
        # Should still be VCV until next breath boundary
        self.assertEqual(sim.settings.mode, "VCV")
        _run_for_seconds(sim, 10.0)
        self.assertEqual(sim.settings.mode, "PCV")


if __name__ == "__main__":
    unittest.main()
