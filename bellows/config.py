"""Configuration helpers for constructing Bellows simulations."""

from __future__ import annotations

from dataclasses import dataclass, replace

from bellows.simulation.engine import VentilationSimulation
from bellows.simulation.presets import LUNG_MODELS, PatientPreset, presets_for
from bellows.simulation.state import PatientMechanics, VentilatorSettings
from bellows.ventilator.registry import VENTILATOR_MODES


@dataclass(frozen=True)
class SimulationConfig:
    """Serializable-ish startup configuration for a simulation run."""

    settings: VentilatorSettings
    patient: PatientMechanics
    patient_preset_name: str

    def build_simulation(self) -> VentilationSimulation:
        return VentilationSimulation(settings=self.settings, patient=self.patient)


def build_simulation_config(
    *,
    mode: str | None = None,
    vt_ml: float | None = None,
    rr_bpm: float | None = None,
    pinsp_cm_h2o: float | None = None,
    peep_cm_h2o: float | None = None,
    ie: str | None = None,
    p_high_cm_h2o: float | None = None,
    p_low_cm_h2o: float | None = None,
    t_high_s: float | None = None,
    t_low_s: float | None = None,
    expiratory_valve_resistance_cm_h2o_s_per_l: float | None = None,
    pressure_rise_time_s: float | None = None,
    lung_model: str | None = None,
    preset: str | None = None,
) -> SimulationConfig:
    """Build validated simulation state from external configuration values."""

    settings = _build_settings(
        mode=mode,
        vt_ml=vt_ml,
        rr_bpm=rr_bpm,
        pinsp_cm_h2o=pinsp_cm_h2o,
        peep_cm_h2o=peep_cm_h2o,
        ie=ie,
        p_high_cm_h2o=p_high_cm_h2o,
        p_low_cm_h2o=p_low_cm_h2o,
        t_high_s=t_high_s,
        t_low_s=t_low_s,
        expiratory_valve_resistance_cm_h2o_s_per_l=(
            expiratory_valve_resistance_cm_h2o_s_per_l
        ),
        pressure_rise_time_s=pressure_rise_time_s,
    )
    patient_preset = _select_patient_preset(lung_model, preset)
    return SimulationConfig(
        settings=settings,
        patient=patient_preset.mechanics,
        patient_preset_name=patient_preset.name,
    )


def parse_ie_ratio(value: str) -> tuple[float, float]:
    """Parse an I:E ratio into numeric inspiration/expiration parts."""

    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("I:E ratio must use the form I:E, for example 1:2")

    try:
        inspiratory = float(parts[0])
        expiratory = float(parts[1])
    except ValueError as exc:
        raise ValueError("I:E ratio values must be numbers") from exc

    if inspiratory <= 0.0 or expiratory <= 0.0:
        raise ValueError("I:E ratio values must be greater than zero")
    return inspiratory, expiratory


def _build_settings(
    *,
    mode: str | None,
    vt_ml: float | None,
    rr_bpm: float | None,
    pinsp_cm_h2o: float | None,
    peep_cm_h2o: float | None,
    ie: str | None,
    p_high_cm_h2o: float | None,
    p_low_cm_h2o: float | None,
    t_high_s: float | None,
    t_low_s: float | None,
    expiratory_valve_resistance_cm_h2o_s_per_l: float | None,
    pressure_rise_time_s: float | None,
) -> VentilatorSettings:
    settings = VentilatorSettings()
    updates: dict[str, float | str] = {}

    if mode is not None:
        normalized = mode.upper()
        if normalized not in VENTILATOR_MODES:
            raise ValueError(
                f"Unknown ventilator mode {mode!r}; choose one of "
                f"{', '.join(VENTILATOR_MODES)}"
            )
        updates["mode"] = normalized

    _set_if_present(updates, "vt_ml", vt_ml)
    _set_if_present(updates, "rr_bpm", rr_bpm)
    _set_if_present(updates, "pinsp_cm_h2o", pinsp_cm_h2o)
    _set_if_present(updates, "peep_cm_h2o", peep_cm_h2o)
    _set_if_present(updates, "p_high_cm_h2o", p_high_cm_h2o)
    _set_if_present(updates, "p_low_cm_h2o", p_low_cm_h2o)
    _set_if_present(updates, "t_high_s", t_high_s)
    _set_if_present(updates, "t_low_s", t_low_s)
    _set_if_present(
        updates,
        "expiratory_valve_resistance_cm_h2o_s_per_l",
        expiratory_valve_resistance_cm_h2o_s_per_l,
    )
    _set_if_present(updates, "pressure_rise_time_s", pressure_rise_time_s)

    if ie is not None:
        ie_i, ie_e = parse_ie_ratio(ie)
        updates["ie_i"] = ie_i
        updates["ie_e"] = ie_e

    return replace(settings, **updates)


def _select_patient_preset(
    lung_model: str | None,
    preset_name: str | None,
) -> PatientPreset:
    model_name = (
        _match_choice(lung_model, LUNG_MODELS, "lung model")
        if lung_model
        else "Linear"
    )
    presets = presets_for(model_name)

    if preset_name is None:
        return presets[0]

    for preset in presets:
        if preset.name.casefold() == preset_name.casefold():
            return preset

    choices = ", ".join(preset.name for preset in presets)
    raise ValueError(
        f"Unknown preset {preset_name!r} for {model_name}; choose one of {choices}"
    )


def _match_choice(value: str, choices: tuple[str, ...], label: str) -> str:
    for choice in choices:
        if choice.casefold() == value.casefold():
            return choice
    raise ValueError(
        f"Unknown {label} {value!r}; choose one of {', '.join(choices)}"
    )


def _set_if_present(
    updates: dict[str, float | str],
    field_name: str,
    value: float | None,
) -> None:
    if value is not None:
        updates[field_name] = value
