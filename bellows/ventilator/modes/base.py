"""Shared contracts and helpers for ventilator modes."""

from __future__ import annotations

from dataclasses import dataclass
from math import exp
from typing import Protocol

from bellows.simulation.state import PatientMechanics, VentilatorSettings


@dataclass(frozen=True)
class ModeStep:
    phase: str
    flow_l_s: float
    pressure_cm_h2o: float
    lung_volume_l: float


class VentilatorMode(Protocol):
    name: str

    def step(
        self,
        settings: VentilatorSettings,
        patient: PatientMechanics,
        phase_time_s: float,
        lung_volume_l: float,
        dt_s: float,
    ) -> ModeStep:
        ...


def passive_expiration(
    settings: VentilatorSettings,
    patient: PatientMechanics,
    lung_volume_l: float,
    dt_s: float,
) -> ModeStep:
    tau_s = max(patient.time_constant_s, 0.05)
    next_volume_l = max(0.0, lung_volume_l * exp(-dt_s / tau_s))
    flow_l_s = (next_volume_l - lung_volume_l) / dt_s
    pressure_cm_h2o = airway_pressure(settings, patient, next_volume_l, flow_l_s)
    return ModeStep(
        phase="expiration",
        flow_l_s=flow_l_s,
        pressure_cm_h2o=pressure_cm_h2o,
        lung_volume_l=next_volume_l,
    )


def airway_pressure(
    settings: VentilatorSettings,
    patient: PatientMechanics,
    lung_volume_l: float,
    flow_l_s: float,
) -> float:
    elastic = lung_volume_l / patient.compliance_l_per_cm_h2o
    resistive = flow_l_s * patient.resistance_cm_h2o_s_per_l
    pressure = elastic + resistive + settings.peep_cm_h2o
    return max(settings.peep_cm_h2o, pressure)
