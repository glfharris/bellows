"""Deterministic first-pass volume-control ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)
from bellows.ventilator.modes.pcv import PressureControl
from bellows.ventilator.modes.vcv import VolumeControl


MODES = {
    "VCV": VolumeControl(),
    "PCV": PressureControl(),
}


@dataclass
class VentilationSimulation:
    """Simple single-compartment ventilation simulator."""

    settings: VentilatorSettings = field(default_factory=VentilatorSettings)
    patient: PatientMechanics = field(default_factory=PatientMechanics)
    pending_settings: VentilatorSettings | None = None
    time_s: float = 0.0
    breath_time_s: float = 0.0
    lung_volume_l: float = 0.0
    breath: int = 0

    def reset(self) -> None:
        self.time_s = 0.0
        self.breath_time_s = 0.0
        self.lung_volume_l = 0.0
        self.breath = 0
        self.pending_settings = None

    def queue_settings(self, settings: VentilatorSettings) -> None:
        self.pending_settings = settings

    def step(self, dt_s: float) -> SimulationSample:
        phase_time_s = self.breath_time_s
        breath = self.breath

        mode = MODES.get(self.settings.mode, MODES["VCV"])
        step = mode.step(
            self.settings,
            self.patient,
            phase_time_s,
            self.lung_volume_l,
            dt_s,
        )
        self.lung_volume_l = step.lung_volume_l
        co2_kpa = self._co2(phase_time_s)

        sample = SimulationSample(
            time_s=self.time_s,
            pressure_cm_h2o=step.pressure_cm_h2o,
            flow_l_min=step.flow_l_s * 60.0,
            volume_ml=self.lung_volume_l * 1000.0,
            co2_kpa=co2_kpa,
            phase=step.phase,
            breath=breath,
        )

        self.time_s += dt_s
        self.breath_time_s += dt_s
        while self.breath_time_s >= self.settings.cycle_s:
            self.breath_time_s -= self.settings.cycle_s
            self.breath += 1
            if self.pending_settings is not None:
                self.settings = self.pending_settings
                self.pending_settings = None

        return sample

    def _co2(self, phase_time_s: float) -> float:
        if phase_time_s < self.settings.inspiratory_time_s:
            return 0.0

        exp_elapsed_s = phase_time_s - self.settings.inspiratory_time_s
        exp_fraction = exp_elapsed_s / max(self.settings.expiratory_time_s, 0.01)

        if exp_fraction < 0.12:
            return 0.0
        if exp_fraction < 0.32:
            upstroke = (exp_fraction - 0.12) / 0.20
            return self.patient.etco2_kpa * upstroke

        plateau_fraction = (exp_fraction - 0.32) / 0.68
        return self.patient.etco2_kpa * (0.90 + 0.10 * min(1.0, plateau_fraction))
