"""Built-in patient mechanics presets."""

from __future__ import annotations

from dataclasses import dataclass

from bellows.simulation.state import PatientMechanics


@dataclass(frozen=True)
class PatientPreset:
    name: str
    mechanics: PatientMechanics


PATIENT_PRESETS = [
    PatientPreset(
        "Normal",
        PatientMechanics(
            compliance_l_per_cm_h2o=0.05,
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Stiff",
        PatientMechanics(
            compliance_l_per_cm_h2o=0.025,
            resistance_cm_h2o_s_per_l=10.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Restrictive",
        PatientMechanics(
            compliance_l_per_cm_h2o=0.02,
            resistance_cm_h2o_s_per_l=12.0,
            etco2_kpa=5.1,
        ),
    ),
    PatientPreset(
        "Obstructed",
        PatientMechanics(
            compliance_l_per_cm_h2o=0.06,
            resistance_cm_h2o_s_per_l=20.0,
            etco2_kpa=5.6,
        ),
    ),
    PatientPreset(
        "Severe obstruction",
        PatientMechanics(
            compliance_l_per_cm_h2o=0.07,
            resistance_cm_h2o_s_per_l=35.0,
            etco2_kpa=6.2,
        ),
    ),
]
