"""Pressure-control ventilation."""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.mechanics import VentilatorIntent
from bellows.simulation.state import VentilatorSettings
from bellows.ventilator.modes.base import (
    VentilatorMode,
    passive_expiration,
    pressure_target_phase,
)


class PressureControl(VentilatorMode):
    name = "PCV"
    control_keys = ("target", "rr", "peep", "ie")
    control_labels = {"target": "Pinsp"}

    def target_status(self, settings: VentilatorSettings) -> str:
        return f"Pinsp {settings.pinsp_cm_h2o:.0f} cmH2O"

    def step(
        self,
        settings: VentilatorSettings,
        phase_time_s: float,
    ) -> VentilatorIntent:
        if phase_time_s >= settings.inspiratory_time_s:
            return passive_expiration(
                settings,
                expiratory_valve_elapsed_s=(
                    phase_time_s - settings.inspiratory_time_s
                ),
            )

        return _pcv_inspiration(
            settings,
            settings.pinsp_cm_h2o,
        )


def _pcv_inspiration(
    settings: VentilatorSettings,
    pinsp_cm_h2o: float,
) -> VentilatorIntent:
    """PCV-style decelerating inspiration. Used by PCV and PRVC.

    ``pinsp_cm_h2o`` is the driving pressure above PEEP; the absolute target
    plateau pressure is ``PEEP + pinsp``.
    """

    target_total_pressure = settings.peep_cm_h2o + pinsp_cm_h2o
    return pressure_target_phase(
        target_pressure_cm_h2o=target_total_pressure,
        pressure_rise_time_s=settings.pressure_rise_time_s,
        phase=PHASE_INSPIRATION,
    )
