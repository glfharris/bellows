"""State and settings used by the ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class VentilatorSettings:
    """Core settings for initial volume-control ventilation."""

    mode: str = "VCV"
    rr_bpm: float = 14.0
    vt_ml: float = 500.0
    pinsp_cm_h2o: float = 15.0
    peep_cm_h2o: float = 5.0
    ie_i: float = 1.0
    ie_e: float = 2.0

    @property
    def cycle_s(self) -> float:
        return 60.0 / self.rr_bpm

    @property
    def inspiratory_time_s(self) -> float:
        return self.cycle_s * self.ie_i / (self.ie_i + self.ie_e)

    @property
    def expiratory_time_s(self) -> float:
        return self.cycle_s - self.inspiratory_time_s

    @property
    def vt_l(self) -> float:
        return self.vt_ml / 1000.0

    @property
    def inspiratory_flow_l_s(self) -> float:
        return self.vt_l / self.inspiratory_time_s


@dataclass(frozen=True)
class PatientMechanics:
    """Simple single-compartment lung mechanics."""

    compliance_l_per_cm_h2o: float = 0.05
    resistance_cm_h2o_s_per_l: float = 10.0
    etco2_kpa: float = 5.1

    @property
    def time_constant_s(self) -> float:
        return self.compliance_l_per_cm_h2o * self.resistance_cm_h2o_s_per_l


@dataclass(frozen=True)
class SimulationSample:
    """One timestamped simulation sample."""

    time_s: float
    pressure_cm_h2o: float
    flow_l_min: float
    volume_ml: float
    co2_kpa: float
    phase: str
    breath: int
