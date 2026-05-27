"""Airway pressure release ventilation (passive).

Airway pressure alternates between ``p_high`` (held for ``t_high``) and
``p_low`` (released for ``t_low``). The patient model has no spontaneous
breathing yet, so the trace shows the mandatory pressure swings only.
"""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.mechanics import VentilatorIntent
from bellows.simulation.state import VentilatorSettings
from bellows.ventilator.modes.base import (
    VentilatorMode,
    passive_expiration,
    pressure_target_phase,
)


class AirwayPressureReleaseVentilation(VentilatorMode):
    name = "APRV"
    control_keys = ("p_high", "p_low", "t_high", "t_low")

    def resting_floor_pressure(self, settings: VentilatorSettings) -> float:
        return settings.p_low_cm_h2o

    def pending_summary(self, settings: VentilatorSettings) -> str:
        return (
            f"P_high {settings.p_high_cm_h2o:.0f}  "
            f"P_low {settings.p_low_cm_h2o:.0f}  "
            f"T_high {settings.t_high_s:.1f}  "
            f"T_low {settings.t_low_s:.1f}"
        )

    def step(
        self,
        settings: VentilatorSettings,
        phase_time_s: float,
    ) -> VentilatorIntent:
        if phase_time_s < settings.t_high_s:
            return _high_phase(
                settings,
            )

        return passive_expiration(
            settings,
            floor_pressure_cm_h2o=settings.p_low_cm_h2o,
            expiratory_valve_elapsed_s=phase_time_s - settings.t_high_s,
        )


def _high_phase(
    settings: VentilatorSettings,
) -> VentilatorIntent:
    return pressure_target_phase(
        target_pressure_cm_h2o=settings.p_high_cm_h2o,
        pressure_rise_time_s=settings.pressure_rise_time_s,
        phase=PHASE_INSPIRATION,
    )
