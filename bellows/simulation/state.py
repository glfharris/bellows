"""State and settings used by the ventilation simulation."""

from __future__ import annotations

from dataclasses import dataclass, field

from bellows.simulation.lung_model import LinearLung, LungModel


@dataclass(frozen=True)
class VentilatorSettings:
    """Settings for all supported ventilator modes.

    Modes only consume the fields they care about. For VCV/PCV/PRVC the
    cycle is driven by ``rr_bpm`` and ``ie_*``; for APRV the cycle is
    ``t_high_s + t_low_s`` and the rr/ie fields are ignored.
    """

    mode: str = "VCV"
    rr_bpm: float = 14.0
    vt_ml: float = 500.0
    pinsp_cm_h2o: float = 15.0
    peep_cm_h2o: float = 5.0
    ie_i: float = 1.0
    ie_e: float = 2.0
    p_high_cm_h2o: float = 25.0
    p_low_cm_h2o: float = 5.0
    t_high_s: float = 4.0
    t_low_s: float = 0.6

    def __post_init__(self) -> None:
        if self.rr_bpm <= 0.0:
            raise ValueError("rr_bpm must be greater than zero")
        if self.vt_ml < 0.0:
            raise ValueError("vt_ml must be greater than or equal to zero")
        if self.pinsp_cm_h2o < 0.0:
            raise ValueError("pinsp_cm_h2o must be greater than or equal to zero")
        if self.peep_cm_h2o < 0.0:
            raise ValueError("peep_cm_h2o must be greater than or equal to zero")
        if self.ie_i <= 0.0 or self.ie_e <= 0.0:
            raise ValueError("ie_i and ie_e must be greater than zero")
        if self.p_high_cm_h2o < 0.0 or self.p_low_cm_h2o < 0.0:
            raise ValueError("APRV pressures must be greater than or equal to zero")
        if self.p_high_cm_h2o <= self.p_low_cm_h2o:
            raise ValueError("p_high_cm_h2o must be greater than p_low_cm_h2o")
        if self.t_high_s <= 0.0 or self.t_low_s <= 0.0:
            raise ValueError("t_high_s and t_low_s must be greater than zero")

    @property
    def cycle_s(self) -> float:
        if self.mode == "APRV":
            return self.t_high_s + self.t_low_s
        return 60.0 / self.rr_bpm

    @property
    def inspiratory_time_s(self) -> float:
        if self.mode == "APRV":
            return self.t_high_s
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
    """Simple single-compartment lung mechanics.

    The elastic PV relationship is delegated to ``lung_model``; resistance
    and end-tidal CO2 are still scalar properties. The default is the
    original linear-compliance behaviour for backward compatibility.
    """

    lung_model: LungModel = field(default_factory=lambda: LinearLung(0.05))
    resistance_cm_h2o_s_per_l: float = 10.0
    etco2_kpa: float = 5.1

    def __post_init__(self) -> None:
        if self.resistance_cm_h2o_s_per_l <= 0.0:
            raise ValueError("resistance_cm_h2o_s_per_l must be greater than zero")
        if self.etco2_kpa < 0.0:
            raise ValueError("etco2_kpa must be greater than or equal to zero")


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
