"""FastAPI app for the local Bellows web UI."""

from __future__ import annotations

import threading
from dataclasses import asdict, fields, replace
from pathlib import Path
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from bellows.config import SimulationConfig
from bellows.simulation.lung_model import (
    LinearLung,
    VenegasHysteresisLung,
    VenegasLung,
)
from bellows.simulation.metrics import BreathSummary
from bellows.simulation.presets import LUNG_MODELS, presets_for
from bellows.simulation.state import (
    PatientMechanics,
    SimulationSample,
    VentilatorSettings,
)

STATIC_DIR = Path(__file__).with_name("static")


class WebSimulationState:
    """Thread-safe owner for the simulation used by web endpoints."""

    def __init__(self, config: SimulationConfig) -> None:
        self.config = config
        self.simulation = config.build_simulation()
        self.patient_preset_name = config.patient_preset_name
        self.paused = False
        self.lock = threading.RLock()

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "paused": self.paused,
                "settings": asdict(self.simulation.settings),
                "patient": _patient_payload(
                    self.simulation.patient,
                    self.patient_preset_name,
                ),
                "sample": _sample_payload(self.simulation.current_sample()),
                "last_breath_summary": _summary_payload(
                    self.simulation.last_breath_summary
                ),
                "previous_breath_summary": _summary_payload(
                    _previous_breath_summary(self.simulation.breath_history)
                ),
                "pending_settings": (
                    asdict(self.simulation.pending_settings)
                    if self.simulation.pending_settings is not None
                    else None
                ),
            }

    def samples(self, *, seconds: float, dt_s: float) -> dict[str, Any]:
        with self.lock:
            if self.paused:
                samples: list[SimulationSample] = []
            else:
                run = self.simulation.run(
                    seconds=seconds,
                    dt_s=dt_s,
                    include_initial=False,
                )
                samples = list(run)
            return {
                "samples": [_sample_payload(sample) for sample in samples],
                "state": self.snapshot(),
            }

    def update_settings(self, updates: dict[str, Any]) -> dict[str, Any]:
        allowed = {field.name for field in fields(VentilatorSettings)}
        clean_updates = {key: value for key, value in updates.items() if key in allowed}
        with self.lock:
            self.simulation.update_settings(**clean_updates)
            return self.snapshot()

    def update_patient(self, updates: dict[str, Any]) -> dict[str, Any]:
        with self.lock:
            patient, preset_name = _updated_patient(
                self.simulation.patient,
                self.patient_preset_name,
                updates,
            )
            self.simulation.update_patient(
                **_patient_updates(self.simulation.patient, patient)
            )
            self.patient_preset_name = preset_name
            return self.snapshot()

    def set_paused(self, paused: bool) -> dict[str, Any]:
        with self.lock:
            self.paused = paused
            return self.snapshot()

    def reset(self) -> dict[str, Any]:
        with self.lock:
            self.simulation.reset()
            return self.snapshot()


def create_app(config: SimulationConfig) -> FastAPI:
    state = WebSimulationState(config)
    app = FastAPI(title="Bellows")

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/state")
    def api_state() -> dict[str, Any]:
        return state.snapshot()

    @app.get("/api/samples")
    def api_samples(seconds: float = 0.05, dt_s: float = 0.01) -> dict[str, Any]:
        try:
            return state.samples(seconds=seconds, dt_s=dt_s)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/settings")
    def api_settings(updates: dict[str, Any]) -> dict[str, Any]:
        try:
            return state.update_settings(updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/patient")
    def api_patient(updates: dict[str, Any]) -> dict[str, Any]:
        try:
            return state.update_patient(updates)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc

    @app.post("/api/pause")
    def api_pause(payload: dict[str, Any]) -> dict[str, Any]:
        return state.set_paused(bool(payload["paused"]))

    @app.post("/api/reset")
    def api_reset() -> dict[str, Any]:
        return state.reset()

    app.mount("/", StaticFiles(directory=STATIC_DIR), name="static")
    return app


def serve_web(
    config: SimulationConfig,
    *,
    host: str = "127.0.0.1",
    port: int = 8765,
) -> None:
    url = f"http://{host}:{port}"
    print(f"Bellows web UI running at {url}")
    uvicorn.run(
        create_app(config),
        host=host,
        port=port,
        log_level="warning",
    )


def _sample_payload(sample: SimulationSample) -> dict[str, Any]:
    return asdict(sample)


def _summary_payload(summary: BreathSummary | None) -> dict[str, Any] | None:
    if summary is None:
        return None
    return {
        "breath": summary.breath,
        "start_time_s": summary.start_time_s,
        "end_time_s": summary.end_time_s,
        "duration_s": summary.duration_s,
        "vt_ml": summary.vt_ml,
        "peak_pressure_cm_h2o": summary.peak_pressure_cm_h2o,
        "mean_pressure_cm_h2o": summary.mean_pressure_cm_h2o,
        "minute_volume_l_min": summary.minute_volume_l_min,
        "etco2_kpa": summary.etco2_kpa,
    }


def _previous_breath_summary(history) -> BreathSummary | None:
    recent = history.recent(2)
    if len(recent) < 2:
        return None
    return recent[0]


def _patient_payload(patient: PatientMechanics, preset_name: str) -> dict[str, Any]:
    return {
        "lung_model": patient.lung_model.name,
        "preset": preset_name,
        "lung_models": list(LUNG_MODELS),
        "presets": [preset.name for preset in presets_for(patient.lung_model.name)],
        "lung_parameters": _lung_parameter_payload(patient),
        "resistance_cm_h2o_s_per_l": patient.resistance_cm_h2o_s_per_l,
        "etco2_kpa": patient.etco2_kpa,
    }


def _lung_parameter_payload(patient: PatientMechanics) -> dict[str, float]:
    lung = patient.lung_model
    if isinstance(lung, LinearLung):
        return {
            "compliance_ml_per_cm_h2o": lung.compliance_l_per_cm_h2o * 1000.0,
        }
    payload = {
        "inflection_cm_h2o": lung.inflection_cm_h2o,
        "slope_width_cm_h2o": lung.slope_width_cm_h2o,
        "recruitable_volume_ml": lung.recruitable_volume_l * 1000.0,
    }
    if isinstance(lung, VenegasHysteresisLung):
        payload["hysteresis_offset_cm_h2o"] = lung.hysteresis_offset_cm_h2o
    return payload


def _updated_patient(
    patient: PatientMechanics,
    preset_name: str,
    updates: dict[str, Any],
) -> tuple[PatientMechanics, str]:
    lung_model_name = str(updates.get("lung_model", patient.lung_model.name))
    if lung_model_name not in LUNG_MODELS:
        raise ValueError(f"Unknown lung model {lung_model_name!r}")
    if lung_model_name != patient.lung_model.name:
        preset = presets_for(lung_model_name)[0]
        patient = preset.mechanics
        preset_name = preset.name

    if "preset" in updates:
        preset = _preset_named(patient.lung_model.name, str(updates["preset"]))
        patient = preset.mechanics
        preset_name = preset.name

    if "resistance_cm_h2o_s_per_l" in updates:
        patient = replace(
            patient,
            resistance_cm_h2o_s_per_l=float(updates["resistance_cm_h2o_s_per_l"]),
        )
        preset_name = "Custom"

    lung = patient.lung_model
    if isinstance(lung, LinearLung) and "compliance_ml_per_cm_h2o" in updates:
        lung = replace(
            lung,
            compliance_l_per_cm_h2o=float(updates["compliance_ml_per_cm_h2o"]) / 1000.0,
        )
        patient = replace(patient, lung_model=lung)
        preset_name = "Custom"
    elif isinstance(lung, (VenegasLung, VenegasHysteresisLung)):
        lung_updates: dict[str, float] = {}
        if "inflection_cm_h2o" in updates:
            lung_updates["inflection_cm_h2o"] = float(updates["inflection_cm_h2o"])
        if "slope_width_cm_h2o" in updates:
            lung_updates["slope_width_cm_h2o"] = float(updates["slope_width_cm_h2o"])
        if "recruitable_volume_ml" in updates:
            lung_updates["recruitable_volume_l"] = (
                float(updates["recruitable_volume_ml"]) / 1000.0
            )
        if (
            isinstance(lung, VenegasHysteresisLung)
            and "hysteresis_offset_cm_h2o" in updates
        ):
            lung_updates["hysteresis_offset_cm_h2o"] = float(
                updates["hysteresis_offset_cm_h2o"]
            )
        if lung_updates:
            patient = replace(patient, lung_model=replace(lung, **lung_updates))
            preset_name = "Custom"

    return patient, preset_name


def _preset_named(lung_model_name: str, preset_name: str):
    for preset in presets_for(lung_model_name):
        if preset.name == preset_name:
            return preset
    raise ValueError(f"Unknown {lung_model_name} preset {preset_name!r}")


def _patient_updates(
    current: PatientMechanics,
    updated: PatientMechanics,
) -> dict[str, object]:
    return {
        field.name: getattr(updated, field.name)
        for field in fields(PatientMechanics)
        if getattr(updated, field.name) != getattr(current, field.name)
    }
