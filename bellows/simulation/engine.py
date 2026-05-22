"""Deterministic first-pass ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

from bellows.simulation.phase import PHASE_EXPIRATION
from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)
from bellows.ventilator.modes.base import LastBreathStats, VentilatorMode
from bellows.ventilator.registry import default_modes


@dataclass
class VentilationSimulation:
    """Simple single-compartment ventilation simulator."""

    settings: VentilatorSettings = field(default_factory=VentilatorSettings)
    patient: PatientMechanics = field(default_factory=PatientMechanics)
    pending_settings: VentilatorSettings | None = None
    time_s: float = 0.0
    breath_time_s: float = 0.0
    lung_volume_l: float = field(default=0.0, init=False)
    breath: int = 0
    modes: dict[str, VentilatorMode] = field(default_factory=default_modes)
    _active_mode_name: str | None = field(default=None, init=False)
    _breath_has_samples: bool = field(default=False, init=False)
    _breath_max_volume_l: float = field(default=0.0, init=False)
    _breath_min_volume_l: float = field(default=0.0, init=False)
    _breath_max_pressure_cm_h2o: float = field(default=0.0, init=False)

    def __post_init__(self) -> None:
        self.lung_volume_l = self._equilibrium_volume()

    def reset(self) -> None:
        self.time_s = 0.0
        self.breath_time_s = 0.0
        self.lung_volume_l = self._equilibrium_volume()
        self.breath = 0
        self.pending_settings = None
        self._active_mode_name = None
        self._reset_breath_stats()

    def _equilibrium_volume(self) -> float:
        return self.patient.lung_model.equilibrium_volume(
            self.settings.peep_cm_h2o, PHASE_EXPIRATION
        )

    def queue_settings(self, settings: VentilatorSettings) -> None:
        self.pending_settings = settings

    def step(self, dt_s: float) -> SimulationSample:
        mode = self._active_mode()
        phase_time_s = self.breath_time_s
        breath = self.breath

        step = mode.step(
            self.settings,
            self.patient,
            phase_time_s,
            self.lung_volume_l,
            dt_s,
        )
        self.lung_volume_l = step.lung_volume_l
        self._observe_breath_sample(step.pressure_cm_h2o, self.lung_volume_l)
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
            self._finish_breath(mode)
            self.breath_time_s -= self.settings.cycle_s
            self.breath += 1
            if self.pending_settings is not None:
                self.settings = self.pending_settings
                self.pending_settings = None
                mode = self._active_mode()

        return sample

    def _active_mode(self) -> VentilatorMode:
        mode = self.modes.get(self.settings.mode)
        if mode is None:
            raise ValueError(
                f"Unknown ventilator mode {self.settings.mode!r}; "
                f"available: {sorted(self.modes)}"
            )
        active_name = mode.name
        if active_name != self._active_mode_name:
            mode.on_activate(self.settings)
            self._active_mode_name = active_name
        return mode

    def _finish_breath(self, mode: VentilatorMode) -> None:
        delivered_vt_l = max(0.0, self._breath_max_volume_l - self._breath_min_volume_l)
        stats = LastBreathStats(
            delivered_vt_l=delivered_vt_l,
            peak_volume_l=self._breath_max_volume_l,
            peak_pressure_cm_h2o=self._breath_max_pressure_cm_h2o,
        )
        mode.on_breath_end(self.settings, self.patient, stats)
        self._reset_breath_stats()

    def _observe_breath_sample(self, pressure_cm_h2o: float, volume_l: float) -> None:
        if not self._breath_has_samples:
            self._breath_has_samples = True
            self._breath_min_volume_l = volume_l
            self._breath_max_volume_l = volume_l
            self._breath_max_pressure_cm_h2o = pressure_cm_h2o
            return
        self._breath_min_volume_l = min(self._breath_min_volume_l, volume_l)
        self._breath_max_volume_l = max(self._breath_max_volume_l, volume_l)
        self._breath_max_pressure_cm_h2o = max(self._breath_max_pressure_cm_h2o, pressure_cm_h2o)

    def _reset_breath_stats(self) -> None:
        self._breath_has_samples = False
        self._breath_max_volume_l = 0.0
        self._breath_min_volume_l = 0.0
        self._breath_max_pressure_cm_h2o = 0.0

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
