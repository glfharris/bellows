"""Validated request bodies for the local web API."""

from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

from bellows.ventilator.registry import VENTILATOR_MODES


class RequestModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", allow_inf_nan=False)


class PartialUpdate(RequestModel):
    @model_validator(mode="before")
    @classmethod
    def reject_null_values(cls, values: Any) -> Any:
        # Omitted fields keep their current values; explicit null is invalid.
        if isinstance(values, dict):
            for name, value in values.items():
                if value is None:
                    raise ValueError(f"{name} cannot be null")
        return values


class SettingsUpdate(PartialUpdate):
    mode: str | None = None
    rr_bpm: float | None = None
    vt_ml: float | None = None
    pinsp_cm_h2o: float | None = None
    peep_cm_h2o: float | None = None
    ie_i: float | None = None
    ie_e: float | None = None
    p_high_cm_h2o: float | None = None
    p_low_cm_h2o: float | None = None
    t_high_s: float | None = None
    t_low_s: float | None = None
    expiratory_valve_resistance_cm_h2o_s_per_l: float | None = None
    pressure_rise_time_s: float | None = None

    @field_validator("mode")
    @classmethod
    def supported_mode(cls, value: str) -> str:
        if value not in VENTILATOR_MODES:
            raise ValueError(f"Unknown ventilator mode {value!r}")
        return value


class PatientUpdate(PartialUpdate):
    lung_model: str | None = None
    preset: str | None = None
    resistance_cm_h2o_s_per_l: float | None = None
    compliance_ml_per_cm_h2o: float | None = None
    inflection_cm_h2o: float | None = None
    slope_width_cm_h2o: float | None = None
    recruitable_volume_ml: float | None = None
    hysteresis_offset_cm_h2o: float | None = None


class PauseRequest(RequestModel):
    paused: bool
