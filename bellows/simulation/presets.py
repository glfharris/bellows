"""Built-in patient mechanics presets, organised per lung model."""

from __future__ import annotations

from dataclasses import dataclass

from bellows.simulation.lung_model import (
    LinearLung,
    LungModel,
    VenegasHysteresisLung,
    VenegasLung,
)
from bellows.simulation.state import PatientMechanics


LUNG_MODELS: tuple[str, ...] = ("Linear", "Venegas", "Venegas+H")


@dataclass(frozen=True)
class PatientPreset:
    name: str
    mechanics: PatientMechanics


LINEAR_PRESETS: list[PatientPreset] = [
    PatientPreset(
        "Normal",
        PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.05),
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Stiff",
        PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.025),
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Restrictive",
        PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.02),
            resistance_cm_h2o_s_per_l=12.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Obstructed",
        PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.06),
            resistance_cm_h2o_s_per_l=20.0,
            etco2_kpa=5.6,
        ),
    ),
    PatientPreset(
        "Severe obstruction",
        PatientMechanics(
            lung_model=LinearLung(compliance_l_per_cm_h2o=0.07),
            resistance_cm_h2o_s_per_l=35.0,
            etco2_kpa=6.2,
        ),
    ),
]


VENEGAS_PRESETS: list[PatientPreset] = [
    PatientPreset(
        "Normal",
        PatientMechanics(
            lung_model=VenegasLung(
                inflection_cm_h2o=18.0,
                slope_width_cm_h2o=5.0,
                recruitable_volume_l=1.2,
            ),
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Recruitable ARDS",
        PatientMechanics(
            lung_model=VenegasLung(
                inflection_cm_h2o=22.0,
                slope_width_cm_h2o=4.0,
                recruitable_volume_l=1.0,
            ),
            resistance_cm_h2o_s_per_l=12.0,
            etco2_kpa=5.4,
        ),
    ),
    PatientPreset(
        "Non-recruitable ARDS",
        PatientMechanics(
            lung_model=VenegasLung(
                inflection_cm_h2o=28.0,
                slope_width_cm_h2o=8.0,
                recruitable_volume_l=0.6,
            ),
            resistance_cm_h2o_s_per_l=14.0,
            etco2_kpa=5.6,
        ),
    ),
    PatientPreset(
        "Obstructed",
        PatientMechanics(
            lung_model=VenegasLung(
                inflection_cm_h2o=15.0,
                slope_width_cm_h2o=6.0,
                recruitable_volume_l=1.4,
            ),
            resistance_cm_h2o_s_per_l=25.0,
            etco2_kpa=5.8,
        ),
    ),
]


VENEGAS_HYSTERESIS_PRESETS: list[PatientPreset] = [
    PatientPreset(
        "Normal",
        PatientMechanics(
            lung_model=VenegasHysteresisLung(
                inflection_cm_h2o=18.0,
                slope_width_cm_h2o=5.0,
                recruitable_volume_l=1.2,
                hysteresis_offset_cm_h2o=3.0,
            ),
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Recruitable ARDS",
        PatientMechanics(
            lung_model=VenegasHysteresisLung(
                inflection_cm_h2o=22.0,
                slope_width_cm_h2o=4.0,
                recruitable_volume_l=1.0,
                hysteresis_offset_cm_h2o=5.0,
            ),
            resistance_cm_h2o_s_per_l=12.0,
            etco2_kpa=5.4,
        ),
    ),
    PatientPreset(
        "Surfactant-deficient",
        PatientMechanics(
            lung_model=VenegasHysteresisLung(
                inflection_cm_h2o=24.0,
                slope_width_cm_h2o=4.0,
                recruitable_volume_l=1.0,
                hysteresis_offset_cm_h2o=7.0,
            ),
            resistance_cm_h2o_s_per_l=12.0,
            etco2_kpa=5.5,
        ),
    ),
]


_PRESETS_BY_MODEL: dict[str, list[PatientPreset]] = {
    "Linear": LINEAR_PRESETS,
    "Venegas": VENEGAS_PRESETS,
    "Venegas+H": VENEGAS_HYSTERESIS_PRESETS,
}


def presets_for(lung_model_name: str) -> list[PatientPreset]:
    return _PRESETS_BY_MODEL.get(lung_model_name, LINEAR_PRESETS)


# Backward-compat alias: the original module exported PATIENT_PRESETS as the
# canonical preset list. Keep it pointed at LINEAR_PRESETS so existing imports
# still resolve while the UI migrates to the per-model lookup.
PATIENT_PRESETS = LINEAR_PRESETS
