"""Pressure-regulated volume control.

PRVC behaves like PCV during a single breath (decelerating inspiratory flow
to a target plateau pressure) but adjusts that plateau pressure between
breaths so the delivered tidal volume tracks ``settings.vt_ml``.
"""

from __future__ import annotations

from bellows.simulation.lung_model import PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.modes.base import (
    LastBreathStats,
    ModeStep,
    VentilatorMode,
    passive_expiration,
)
from bellows.ventilator.modes.pcv import _pcv_inspiration


MIN_PINSP_CM_H2O = 5.0
MAX_PINSP_CM_H2O = 40.0
MAX_STEP_CM_H2O = 3.0


class PressureRegulatedVolumeControl(VentilatorMode):
    name = "PRVC"

    def __init__(self) -> None:
        # on_activate overwrites this from settings before the first step.
        self.applied_pinsp_cm_h2o: float = 15.0

    def on_activate(self, settings: VentilatorSettings) -> None:
        self.applied_pinsp_cm_h2o = _clamp(
            settings.pinsp_cm_h2o,
            MIN_PINSP_CM_H2O,
            MAX_PINSP_CM_H2O,
        )

    def on_breath_end(
        self,
        settings: VentilatorSettings,
        patient: PatientMechanics,
        stats: LastBreathStats,
    ) -> None:
        target_vt_l = settings.vt_l
        if target_vt_l <= 0.0 or stats.delivered_vt_l <= 0.0:
            return

        # Proportional correction against the actual delivered VT, scaled by
        # the local slope of the lung's PV curve at the volume the lung was
        # operating at last breath. That captures both compliance changes
        # and where on the sigmoid the patient is sitting (so PEEP-driven
        # recruitment naturally reduces the Pinsp PRVC asks for).
        error_l = target_vt_l - stats.delivered_vt_l
        local_slope = patient.lung_model.elastic_slope(
            stats.peak_volume_l, PHASE_INSPIRATION
        )
        delta = error_l * local_slope
        delta = _clamp(delta, -MAX_STEP_CM_H2O, MAX_STEP_CM_H2O)
        self.applied_pinsp_cm_h2o = _clamp(
            self.applied_pinsp_cm_h2o + delta,
            MIN_PINSP_CM_H2O,
            MAX_PINSP_CM_H2O,
        )

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
            self.applied_pinsp_cm_h2o,
            lung_volume_l,
            dt_s,
        )


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
