"""Airway pressure release ventilation (passive).

Airway pressure alternates between ``p_high`` (held for ``t_high``) and
``p_low`` (released for ``t_low``). The patient model has no spontaneous
breathing yet, so the trace shows the mandatory pressure swings only.
"""

from __future__ import annotations

from bellows.simulation.lung_model import PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import ModeStep, VentilatorMode, passive_expiration


class AirwayPressureReleaseVentilation(VentilatorMode):
    name = "APRV"

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
    elastic_cm_h2o = patient.lung_model.elastic_pressure(
        lung_volume_l, PHASE_INSPIRATION
    )
    # Allow negative flow so the lung can deflate toward p_high if it was
    # over-distended at the start of the high phase.
    driving_pressure = settings.p_high_cm_h2o - elastic_cm_h2o
    flow_l_s = driving_pressure / max(patient.resistance_cm_h2o_s_per_l, 1e-3)
    next_volume_l = max(0.0, lung_volume_l + flow_l_s * dt_s)

    return ModeStep(
        phase="inspiration",
        flow_l_s=flow_l_s,
        pressure_cm_h2o=settings.p_high_cm_h2o,
        lung_volume_l=next_volume_l,
    )
