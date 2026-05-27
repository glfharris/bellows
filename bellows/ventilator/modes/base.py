"""Shared contracts and intent helpers for ventilator modes."""

from __future__ import annotations

from bellows.simulation.metrics import BreathSummary
from bellows.simulation.phase import PHASE_EXPIRATION
from bellows.simulation.mechanics import VentilatorIntent
from bellows.simulation.state import PatientMechanics, VentilatorSettings


class VentilatorMode:
    """Base class for ventilator modes."""

    name: str = "BASE"
    control_keys: tuple[str, ...] = ()
    control_labels: dict[str, str] = {}

    def control_label(self, key: str) -> str | None:
        return self.control_labels.get(key)

    def target_status(self, settings: VentilatorSettings) -> str:
        return f"VT {settings.vt_ml:.0f} mL"

    def pending_summary(self, settings: VentilatorSettings) -> str:
        return (
            f"RR {settings.rr_bpm:.0f}  "
            f"PEEP {settings.peep_cm_h2o:.0f}  "
            f"I:E {settings.ie_i:.0f}:{settings.ie_e:g}"
        )

    def resting_floor_pressure(self, settings: VentilatorSettings) -> float:
        return settings.peep_cm_h2o

    def on_activate(self, settings: VentilatorSettings) -> None:
        """Called when this mode becomes active. Reset any internal state."""

    def on_breath_end(
        self,
        settings: VentilatorSettings,
        patient: PatientMechanics,
        stats: BreathSummary,
    ) -> None:
        """Called at the end of each breath with the breath's stats."""

    def step(
        self,
        settings: VentilatorSettings,
        phase_time_s: float,
    ) -> VentilatorIntent:
        raise NotImplementedError


def passive_expiration(
    settings: VentilatorSettings,
    floor_pressure_cm_h2o: float | None = None,
    expiratory_valve_elapsed_s: float | None = None,
) -> VentilatorIntent:
    floor = (
        settings.peep_cm_h2o
        if floor_pressure_cm_h2o is None
        else floor_pressure_cm_h2o
    )
    return VentilatorIntent(
        phase=PHASE_EXPIRATION,
        ventilator_flow_l_s=0.0,
        expiratory_floor_pressure_cm_h2o=floor,
        expiratory_valve_resistance_cm_h2o_s_per_l=(
            settings.expiratory_valve_resistance_cm_h2o_s_per_l
        ),
        expiratory_valve_open=True,
        expiratory_valve_elapsed_s=expiratory_valve_elapsed_s,
    )


def pressure_target_phase(
    *,
    target_pressure_cm_h2o: float,
    pressure_rise_time_s: float,
    phase: str,
) -> VentilatorIntent:
    return VentilatorIntent(
        phase=phase,
        target_pressure_cm_h2o=target_pressure_cm_h2o,
        pressure_response_time_s=pressure_rise_time_s,
    )
