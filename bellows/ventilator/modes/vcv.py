"""Volume-control ventilation."""

from __future__ import annotations

from bellows.simulation.phase import PHASE_INSPIRATION
from bellows.simulation.mechanics import VentilatorIntent
from bellows.simulation.state import VentilatorSettings
from bellows.ventilator.modes.base import (
    VentilatorMode,
    passive_expiration,
)


class VolumeControl(VentilatorMode):
    name = "VCV"
    control_keys = ("target", "rr", "peep", "ie")
    control_labels = {"target": "VT target"}

    def step(
        self,
        settings: VentilatorSettings,
        phase_time_s: float,
    ) -> VentilatorIntent:
        if phase_time_s >= settings.inspiratory_time_s:
            return passive_expiration(
                settings,
                expiratory_valve_elapsed_s=(
                    phase_time_s - settings.inspiratory_time_s
                ),
            )

        flow_l_s = settings.inspiratory_flow_l_s
        return VentilatorIntent(
            phase=PHASE_INSPIRATION,
            ventilator_flow_l_s=flow_l_s,
        )
