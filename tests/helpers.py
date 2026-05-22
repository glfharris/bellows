"""Shared helpers for the test suite.

Tests in this project are directional: they drive the full simulation for
a few breaths and assert qualitative behaviour. These helpers exist so
each test file doesn't need to re-define the same loop and aggregation.
"""

from __future__ import annotations

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.state import SimulationSample


def run_for_seconds(
    sim: VentilationSimulation, seconds: float, dt_s: float = 0.01
) -> list[SimulationSample]:
    """Drive ``sim`` for ``seconds`` of simulated time and return every sample."""
    return [sim.step(dt_s) for _ in range(int(seconds / dt_s))]


def peak_pressure(
    sim: VentilationSimulation, seconds: float = 15.0, dt_s: float = 0.01
) -> float:
    """Drive ``sim`` and return the highest airway pressure observed."""
    return max(s.pressure_cm_h2o for s in run_for_seconds(sim, seconds, dt_s))


def per_breath_max(samples: list[SimulationSample], attr: str) -> dict[int, float]:
    """Per-breath maximum of an attribute on each sample."""
    by_breath: dict[int, float] = {}
    for s in samples:
        value = getattr(s, attr)
        by_breath[s.breath] = max(by_breath.get(s.breath, value), value)
    return by_breath


def per_breath_tidal(samples: list[SimulationSample], attr: str) -> dict[int, float]:
    """Per-breath ``max - min`` of an attribute. Useful for delivered VT."""
    mins: dict[int, float] = {}
    maxs: dict[int, float] = {}
    for s in samples:
        value = getattr(s, attr)
        mins[s.breath] = min(mins.get(s.breath, value), value)
        maxs[s.breath] = max(maxs.get(s.breath, value), value)
    return {b: maxs[b] - mins[b] for b in mins}
