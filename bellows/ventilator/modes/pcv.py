"""Pressure-control ventilation."""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import (
    ModeStep,
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
        patient: PatientMechanics,
        phase_time_s: float,
        lung_volume_l: float,
        dt_s: float,
    ) -> ModeStep:
        if phase_time_s >= settings.inspiratory_time_s:
            return passive_expiration(settings, patient, lung_volume_l, dt_s)

        return _pcv_inspiration(
            settings,
            patient,
            settings.pinsp_cm_h2o,
            lung_volume_l,
            dt_s,
        )


def _pcv_inspiration(
    settings: VentilatorSettings,
    patient: PatientMechanics,
    pinsp_cm_h2o: float,
    lung_volume_l: float,
    dt_s: float,
) -> ModeStep:
    """PCV-style decelerating inspiration. Used by PCV and PRVC.

    ``pinsp_cm_h2o`` is the driving pressure above PEEP; the absolute target
    plateau pressure is ``PEEP + pinsp``.
    """

    target_total_pressure = settings.peep_cm_h2o + pinsp_cm_h2o
    return pressure_target_phase(
        patient,
        target_pressure_cm_h2o=target_total_pressure,
        phase=PHASE_INSPIRATION,
        lung_volume_l=lung_volume_l,
        dt_s=dt_s,
    )
