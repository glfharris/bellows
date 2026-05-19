"""Shared contracts and helpers for ventilator modes.

The airway pressure equation under the absolute-volume convention:

    Paw = P_elastic(V, phase) + R * Flow

PEEP no longer appears as an additive offset — it's just the airway
pressure the ventilator holds at end-expiration. The lung settles at
whatever volume satisfies ``P_elastic(V_eq) = PEEP``.
"""

from __future__ import annotations

from dataclasses import dataclass

from bellows.simulation.lung_model import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.state import PatientMechanics, VentilatorSettings


@dataclass(frozen=True)
class ModeStep:
    phase: str
    flow_l_s: float
    pressure_cm_h2o: float
    lung_volume_l: float


@dataclass(frozen=True)
class LastBreathStats:
    """Summary of the breath that just completed."""

    delivered_vt_l: float
    peak_volume_l: float
    peak_pressure_cm_h2o: float


class VentilatorMode:
    """Base class for ventilator modes."""

    name: str = "BASE"

    def on_activate(self, settings: VentilatorSettings) -> None:
        """Called when this mode becomes active. Reset any internal state."""

    def on_breath_end(
        self,
        settings: VentilatorSettings,
        patient: PatientMechanics,
        stats: LastBreathStats,
    ) -> None:
        """Called at the end of each breath with the breath's stats."""

    def step(
        self,
        settings: VentilatorSettings,
        patient: PatientMechanics,
        phase_time_s: float,
        lung_volume_l: float,
        dt_s: float,
    ) -> ModeStep:
        raise NotImplementedError


def passive_expiration(
    settings: VentilatorSettings,
    patient: PatientMechanics,
    lung_volume_l: float,
    dt_s: float,
    floor_pressure_cm_h2o: float | None = None,
) -> ModeStep:
    """Forward-Euler expiration toward ``floor_pressure_cm_h2o``.

    The ventilator holds airway pressure at the floor (PEEP by default).
    Flow is driven by the gradient between the lung's elastic recoil and
    the floor, through the airway resistance:

        Flow = (floor - P_elastic(V)) / R

    At equilibrium the lung settles to the volume where
    ``P_elastic(V_eq) = floor``.
    """

    floor = settings.peep_cm_h2o if floor_pressure_cm_h2o is None else floor_pressure_cm_h2o
    elastic_cm_h2o = patient.lung_model.elastic_pressure(
        lung_volume_l, PHASE_EXPIRATION
    )
    driving_cm_h2o = floor - elastic_cm_h2o
    flow_l_s = driving_cm_h2o / max(patient.resistance_cm_h2o_s_per_l, 1e-3)
    next_volume_l = max(0.0, lung_volume_l + flow_l_s * dt_s)
    pressure_cm_h2o = max(
        floor,
        patient.lung_model.elastic_pressure(next_volume_l, PHASE_EXPIRATION)
        + flow_l_s * patient.resistance_cm_h2o_s_per_l,
    )
    return ModeStep(
        phase="expiration",
        flow_l_s=flow_l_s,
        pressure_cm_h2o=pressure_cm_h2o,
        lung_volume_l=next_volume_l,
    )


def airway_pressure(
    patient: PatientMechanics,
    lung_volume_l: float,
    flow_l_s: float,
    phase: str = PHASE_INSPIRATION,
    floor: float = 0.0,
) -> float:
    elastic = patient.lung_model.elastic_pressure(lung_volume_l, phase)
    resistive = flow_l_s * patient.resistance_cm_h2o_s_per_l
    return max(floor, elastic + resistive)
