"""Volume-control ventilation."""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import (
    ModeStep,
    VentilatorMode,
    airway_pressure,
    passive_expiration,
)


class VolumeControl(VentilatorMode):
    name = "VCV"
    control_keys = ("target", "rr", "peep", "ie")
    control_labels = {"target": "VT target"}

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

        flow_l_s = settings.inspiratory_flow_l_s
        next_volume_l = lung_volume_l + flow_l_s * dt_s
        pressure_cm_h2o = airway_pressure(
            patient,
            next_volume_l,
            flow_l_s,
            floor=settings.peep_cm_h2o,
        )
        return ModeStep(
            phase=PHASE_INSPIRATION,
            flow_l_s=flow_l_s,
            pressure_cm_h2o=pressure_cm_h2o,
            lung_volume_l=next_volume_l,
        )
