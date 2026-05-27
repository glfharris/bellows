"""Shared physical mechanics for the ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass
from math import ceil, exp

from bellows.simulation.state import PatientMechanics


PRESSURE_RESPONSE_SETTLING_CONSTANT = 3.0
CIRCUIT_COMPLIANCE_L_PER_CM_H2O = 0.002
CIRCUIT_PRESSURE_RESPONSE_TIME_S = 0.04
EXPIRATORY_VALVE_OPENING_TIME_S = 0.06
MAX_MECHANICS_SUBSTEP_S = 0.001


@dataclass(frozen=True)
class VentilatorIntent:
    """Ventilator command for one phase subinterval.

    This is deliberately phrased as things a ventilator can manipulate:
    delivered flow, pressure target, expiratory valve floor/resistance, and
    valve opening state. The mechanics solver turns that intent into actual
    Paw, lung flow, and lung volume.
    """

    phase: str
    ventilator_flow_l_s: float = 0.0
    target_pressure_cm_h2o: float | None = None
    pressure_response_time_s: float = CIRCUIT_PRESSURE_RESPONSE_TIME_S
    expiratory_floor_pressure_cm_h2o: float = 0.0
    expiratory_valve_resistance_cm_h2o_s_per_l: float = 0.0
    expiratory_valve_open: bool = False
    expiratory_valve_elapsed_s: float | None = None


@dataclass(frozen=True)
class MechanicsStep:
    phase: str
    flow_l_s: float
    pressure_cm_h2o: float
    lung_volume_l: float


def apply_ventilator_intent(
    patient: PatientMechanics,
    intent: VentilatorIntent,
    *,
    lung_volume_l: float,
    airway_pressure_cm_h2o: float,
    dt_s: float,
) -> MechanicsStep:
    """Advance lung volume and Paw through a compliant circuit compartment."""

    if dt_s <= 0.0:
        return MechanicsStep(
            phase=intent.phase,
            flow_l_s=0.0,
            pressure_cm_h2o=airway_pressure_cm_h2o,
            lung_volume_l=lung_volume_l,
        )

    initial_volume_l = lung_volume_l
    volume_l = lung_volume_l
    pressure_cm_h2o = airway_pressure_cm_h2o
    substeps = max(1, ceil(dt_s / MAX_MECHANICS_SUBSTEP_S))
    sub_dt_s = dt_s / substeps
    valve_elapsed_s = intent.expiratory_valve_elapsed_s

    for _ in range(substeps):
        if (
            intent.expiratory_valve_open
            and intent.expiratory_valve_resistance_cm_h2o_s_per_l <= 0.0
        ):
            pressure_cm_h2o = intent.expiratory_floor_pressure_cm_h2o

        elastic_cm_h2o = patient.lung_model.elastic_pressure(
            volume_l,
            intent.phase,
        )
        lung_flow_l_s = (
            pressure_cm_h2o - elastic_cm_h2o
        ) / max(patient.resistance_cm_h2o_s_per_l, 1e-3)
        if volume_l + lung_flow_l_s * sub_dt_s < 0.0:
            lung_flow_l_s = -volume_l / sub_dt_s

        exhaust_flow_l_s = 0.0
        if intent.expiratory_valve_open:
            if intent.expiratory_valve_resistance_cm_h2o_s_per_l <= 0.0:
                exhaust_flow_l_s = max(
                    0.0,
                    intent.ventilator_flow_l_s - lung_flow_l_s,
                )
            else:
                effective_valve_resistance = (
                    intent.expiratory_valve_resistance_cm_h2o_s_per_l
                )
                if valve_elapsed_s is not None:
                    opening_fraction = 1.0 - exp(
                        -PRESSURE_RESPONSE_SETTLING_CONSTANT
                        * max(0.0, valve_elapsed_s)
                        / EXPIRATORY_VALVE_OPENING_TIME_S
                    )
                    effective_valve_resistance /= max(opening_fraction, 0.05)
                exhaust_flow_l_s = max(
                    0.0,
                    (pressure_cm_h2o - intent.expiratory_floor_pressure_cm_h2o)
                    / effective_valve_resistance,
                )

        inflow_l_s = intent.ventilator_flow_l_s
        if intent.target_pressure_cm_h2o is not None:
            command_pressure_cm_h2o = advance_pressure(
                pressure_cm_h2o,
                intent.target_pressure_cm_h2o,
                intent.pressure_response_time_s,
                sub_dt_s,
            )
            inflow_l_s = (
                lung_flow_l_s
                + exhaust_flow_l_s
                + (
                    command_pressure_cm_h2o - pressure_cm_h2o
                ) * CIRCUIT_COMPLIANCE_L_PER_CM_H2O / sub_dt_s
            )

        volume_l = max(0.0, volume_l + lung_flow_l_s * sub_dt_s)
        pressure_cm_h2o += (
            (inflow_l_s - lung_flow_l_s - exhaust_flow_l_s)
            / CIRCUIT_COMPLIANCE_L_PER_CM_H2O
            * sub_dt_s
        )
        if intent.expiratory_valve_open:
            pressure_cm_h2o = max(
                intent.expiratory_floor_pressure_cm_h2o,
                pressure_cm_h2o,
            )
        if valve_elapsed_s is not None:
            valve_elapsed_s += sub_dt_s

    if volume_l < 1e-9:
        volume_l = 0.0
    return MechanicsStep(
        phase=intent.phase,
        flow_l_s=(volume_l - initial_volume_l) / dt_s,
        pressure_cm_h2o=pressure_cm_h2o,
        lung_volume_l=volume_l,
    )


def advance_pressure(
    current_pressure_cm_h2o: float,
    target_pressure_cm_h2o: float,
    response_time_s: float,
    dt_s: float,
) -> float:
    """Advance a first-order pressure command toward a target pressure."""

    if response_time_s <= 0.0:
        return target_pressure_cm_h2o
    if dt_s <= 0.0:
        return current_pressure_cm_h2o
    fraction = 1.0 - exp(
        -PRESSURE_RESPONSE_SETTLING_CONSTANT
        * dt_s
        / response_time_s
    )
    return current_pressure_cm_h2o + (
        target_pressure_cm_h2o - current_pressure_cm_h2o
    ) * fraction
