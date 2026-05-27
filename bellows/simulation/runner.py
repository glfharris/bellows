"""Reusable simulation stepping loops."""

from __future__ import annotations

from collections.abc import Iterator

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.state import SimulationSample


def iter_samples(
    simulation: VentilationSimulation,
    *,
    dt_s: float = 0.01,
    seconds: float | None = None,
    breaths: int | None = None,
) -> Iterator[SimulationSample]:
    """Yield samples until the requested simulated duration or breath count."""

    if dt_s <= 0.0:
        raise ValueError("dt_s must be greater than zero")
    if seconds is not None and seconds < 0.0:
        raise ValueError("seconds must be greater than or equal to zero")
    if breaths is not None and breaths < 0:
        raise ValueError("breaths must be greater than or equal to zero")

    end_time_s = simulation.time_s + seconds if seconds is not None else None
    end_breath = simulation.breath + breaths if breaths is not None else None

    while _should_continue(simulation, end_time_s=end_time_s, end_breath=end_breath):
        step_dt_s = dt_s
        if end_time_s is not None:
            step_dt_s = min(step_dt_s, max(0.0, end_time_s - simulation.time_s))
        for sample in simulation.step_many(step_dt_s):
            yield sample


def run_samples(
    simulation: VentilationSimulation,
    *,
    dt_s: float = 0.01,
    seconds: float | None = None,
    breaths: int | None = None,
) -> list[SimulationSample]:
    return list(
        iter_samples(
            simulation,
            dt_s=dt_s,
            seconds=seconds,
            breaths=breaths,
        )
    )


def _should_continue(
    simulation: VentilationSimulation,
    *,
    end_time_s: float | None,
    end_breath: int | None,
) -> bool:
    if end_time_s is None and end_breath is None:
        return True
    if end_time_s is not None and simulation.time_s >= end_time_s - 1e-9:
        return False
    if end_breath is not None and simulation.breath >= end_breath:
        return False
    return True
