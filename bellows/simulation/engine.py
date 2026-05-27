"""Deterministic first-pass ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any

from bellows.simulation.mechanics import apply_ventilator_intent
from bellows.simulation.metrics import BreathAccumulator, BreathHistory, BreathSummary
from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.simulation.recording import SimulationRun
from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)
from bellows.ventilator.modes.base import VentilatorMode
from bellows.ventilator.registry import default_modes

INTEGRATION_EPSILON_S = 1e-9


@dataclass
class VentilationSimulation:
    """Simple single-compartment ventilation simulator."""

    settings: VentilatorSettings = field(default_factory=VentilatorSettings)
    patient: PatientMechanics = field(default_factory=PatientMechanics)
    pending_settings: VentilatorSettings | None = None
    time_s: float = 0.0
    breath_time_s: float = 0.0
    lung_volume_l: float = field(default=0.0, init=False)
    airway_pressure_cm_h2o: float = field(default=0.0, init=False)
    breath: int = 0
    modes: dict[str, VentilatorMode] = field(default_factory=default_modes)
    breath_history: BreathHistory = field(default_factory=BreathHistory)
    _active_mode_name: str | None = field(default=None, init=False)
    _breath_accumulator: BreathAccumulator = field(
        default_factory=BreathAccumulator,
        init=False,
    )

    def __post_init__(self) -> None:
        self.lung_volume_l = self._equilibrium_volume()
        self.airway_pressure_cm_h2o = self._resting_floor_pressure()

    def reset(self) -> None:
        self.time_s = 0.0
        self.breath_time_s = 0.0
        self.lung_volume_l = self._equilibrium_volume()
        self.airway_pressure_cm_h2o = self._resting_floor_pressure()
        self.breath = 0
        self.pending_settings = None
        self._active_mode_name = None
        self._breath_accumulator.clear()
        self.breath_history.clear()

    @property
    def last_breath_summary(self) -> BreathSummary | None:
        return self.breath_history.last

    def _equilibrium_volume(self) -> float:
        return self.patient.lung_model.equilibrium_volume(
            self._resting_floor_pressure(),
            PHASE_EXPIRATION,
        )

    def _resting_floor_pressure(self) -> float:
        try:
            return self.mode_for(self.settings.mode).resting_floor_pressure(
                self.settings
            )
        except ValueError:
            return self.settings.peep_cm_h2o

    def queue_settings(self, settings: VentilatorSettings) -> None:
        self.pending_settings = settings

    def current_sample(self) -> SimulationSample:
        """Return a sample representing the current simulation state."""

        phase = (
            PHASE_INSPIRATION
            if self.breath_time_s < self.settings.inspiratory_time_s
            else PHASE_EXPIRATION
        )
        return SimulationSample(
            time_s=self.time_s,
            pressure_cm_h2o=self.airway_pressure_cm_h2o,
            flow_l_min=0.0,
            volume_ml=self.lung_volume_l * 1000.0,
            co2_kpa=self._co2(self.breath_time_s),
            phase=phase,
            breath=self.breath,
        )

    def update_settings(
        self,
        *,
        queue: bool = True,
        **updates: Any,
    ) -> VentilatorSettings:
        """Update ventilator settings, queued for the next breath by default."""

        base_settings = (
            self.pending_settings
            if queue and self.pending_settings is not None
            else self.settings
        )
        updated = replace(base_settings, **updates)
        if queue:
            self.queue_settings(updated)
        else:
            self.settings = updated
            self.pending_settings = None
        return updated

    def update_patient(self, **updates: Any) -> PatientMechanics:
        """Update patient mechanics immediately."""

        self.patient = replace(self.patient, **updates)
        return self.patient

    def run(
        self,
        *,
        dt_s: float = 0.01,
        seconds: float | None = None,
        breaths: int | None = None,
        include_initial: bool = True,
    ) -> SimulationRun:
        """Run the simulation and return the generated samples."""

        from bellows.simulation.runner import run_simulation

        return run_simulation(
            self,
            dt_s=dt_s,
            seconds=seconds,
            breaths=breaths,
            include_initial=include_initial,
        )

    def step(self, dt_s: float) -> SimulationSample:
        return self.step_many(dt_s)[-1]

    def step_many(self, dt_s: float) -> list[SimulationSample]:
        remaining_s = dt_s
        samples: list[SimulationSample] = []

        while remaining_s > INTEGRATION_EPSILON_S:
            substep_s = min(remaining_s, self._time_to_next_integration_boundary())
            if substep_s <= INTEGRATION_EPSILON_S:
                substep_s = remaining_s
            samples.append(self._step_subinterval(substep_s))
            remaining_s -= substep_s

        if not samples:
            samples.append(self._step_subinterval(0.0))
        return samples

    def _step_subinterval(self, dt_s: float) -> SimulationSample:
        mode = self._active_mode()
        phase_time_s = self.breath_time_s
        breath = self.breath

        intent = mode.step(
            self.settings,
            phase_time_s,
        )
        step = apply_ventilator_intent(
            self.patient,
            intent,
            lung_volume_l=self.lung_volume_l,
            airway_pressure_cm_h2o=self.airway_pressure_cm_h2o,
            dt_s=dt_s,
        )
        self.lung_volume_l = step.lung_volume_l
        self.airway_pressure_cm_h2o = step.pressure_cm_h2o
        sample_time_s = self.time_s + dt_s
        sample_phase_time_s = phase_time_s + dt_s
        co2_kpa = self._co2(sample_phase_time_s)

        sample = SimulationSample(
            time_s=sample_time_s,
            pressure_cm_h2o=step.pressure_cm_h2o,
            flow_l_min=step.flow_l_s * 60.0,
            volume_ml=self.lung_volume_l * 1000.0,
            co2_kpa=co2_kpa,
            phase=step.phase,
            breath=breath,
        )
        self._breath_accumulator.observe(sample)

        self.time_s += dt_s
        self.breath_time_s += dt_s
        while self.breath_time_s >= self.settings.cycle_s:
            self._finish_breath(mode, end_time_s=self.time_s)
            self.breath_time_s -= self.settings.cycle_s
            self.breath += 1
            if self.pending_settings is not None:
                self.settings = self.pending_settings
                self.pending_settings = None
                mode = self._active_mode()

        return sample

    def _time_to_next_integration_boundary(self) -> float:
        settings = self.settings
        cycle_remaining_s = settings.cycle_s - self.breath_time_s
        candidates = [cycle_remaining_s]
        if self.breath_time_s < settings.inspiratory_time_s:
            candidates.append(settings.inspiratory_time_s - self.breath_time_s)
        positive = [
            candidate
            for candidate in candidates
            if candidate > INTEGRATION_EPSILON_S
        ]
        if not positive:
            return settings.cycle_s
        return min(positive)

    def _active_mode(self) -> VentilatorMode:
        mode = self.mode_for(self.settings.mode)
        active_name = mode.name
        if active_name != self._active_mode_name:
            mode.on_activate(self.settings)
            self._active_mode_name = active_name
        return mode

    def mode_for(self, name: str) -> VentilatorMode:
        mode = self.modes.get(name)
        if mode is None:
            raise ValueError(
                f"Unknown ventilator mode {name!r}; "
                f"available: {sorted(self.modes)}"
            )
        return mode

    def _finish_breath(self, mode: VentilatorMode, *, end_time_s: float) -> None:
        summary = self._breath_accumulator.finish(end_time_s=end_time_s)
        if summary is None:
            return
        self.breath_history.append(summary)
        mode.on_breath_end(self.settings, self.patient, summary)

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
