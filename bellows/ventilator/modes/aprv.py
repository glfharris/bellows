"""Airway pressure release ventilation (passive).

Airway pressure alternates between ``p_high`` (held for ``t_high``) and
``p_low`` (released for ``t_low``). The patient model has no spontaneous
breathing yet, so the trace shows the mandatory pressure swings only.
"""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import (
    ModeStep,
    VentilatorMode,
    passive_expiration,
    pressure_target_phase,
)


class AirwayPressureReleaseVentilation(VentilatorMode):
    name = "APRV"
    control_keys = ("p_high", "p_low", "t_high", "t_low")

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
        patient: PatientMechanics,
        phase_time_s: float,
        lung_volume_l: float,
        dt_s: float,
    ) -> ModeStep:
        if phase_time_s < settings.t_high_s:
            return _high_phase(settings, patient, lung_volume_l, dt_s)

        return passive_expiration(
            settings,
            patient,
            lung_volume_l,
            dt_s,
            floor_pressure_cm_h2o=settings.p_low_cm_h2o,
        )


def _high_phase(
    settings: VentilatorSettings,
    patient: PatientMechanics,
    lung_volume_l: float,
    dt_s: float,
) -> ModeStep:
    return pressure_target_phase(
        patient,
        target_pressure_cm_h2o=settings.p_high_cm_h2o,
        phase=PHASE_INSPIRATION,
        lung_volume_l=lung_volume_l,
        dt_s=dt_s,
    )
