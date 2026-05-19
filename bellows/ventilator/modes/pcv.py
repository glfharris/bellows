"""Pressure-control ventilation."""

from __future__ import annotations

from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import ModeStep, passive_expiration


class PressureControl:
    name = "PCV"

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

        elastic_cm_h2o = lung_volume_l / patient.compliance_l_per_cm_h2o
        driving_pressure = max(0.0, settings.pinsp_cm_h2o - elastic_cm_h2o)
        flow_l_s = driving_pressure / patient.resistance_cm_h2o_s_per_l
        next_volume_l = lung_volume_l + flow_l_s * dt_s
        target_pressure = settings.peep_cm_h2o + settings.pinsp_cm_h2o

        return ModeStep(
            phase="inspiration",
            flow_l_s=flow_l_s,
            pressure_cm_h2o=target_pressure,
            lung_volume_l=next_volume_l,
        )
