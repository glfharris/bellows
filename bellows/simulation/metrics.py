"""Breath-level metrics derived from simulation samples."""

from __future__ import annotations

from dataclasses import dataclass

from bellows.simulation.state import SimulationSample


@dataclass(frozen=True)
class BreathSummary:
    breath: int
    start_time_s: float
    end_time_s: float
    vt_ml: float
    minute_volume_l_min: float
    peak_pressure_cm_h2o: float
    etco2_kpa: float


@dataclass
class BreathMetricsTracker:
    """Track current and last-completed breath metrics from samples."""

    minimum_duration_s: float = 0.01
    current_breath: int | None = None
    current_start_time_s: float = 0.0
    current_latest_time_s: float = 0.0
    current_min_volume_ml: float = 0.0
    current_max_volume_ml: float = 0.0
    current_peak_pressure_cm_h2o: float = 0.0
    current_etco2_kpa: float = 0.0
    completed_vt_ml: float | None = None
    completed_minute_volume_l_min: float | None = None
    completed_peak_pressure_cm_h2o: float | None = None
    completed_etco2_kpa: float | None = None
    last_summary: BreathSummary | None = None

    def observe(self, sample: SimulationSample) -> BreathSummary | None:
        if self.current_breath != sample.breath:
            summary = None
            if self.current_breath is not None:
                summary = self._finalize_current_breath(end_time_s=sample.time_s)

            self.current_breath = sample.breath
            self.current_start_time_s = sample.time_s
            self.current_latest_time_s = sample.time_s
            self.current_min_volume_ml = sample.volume_ml
            self.current_max_volume_ml = sample.volume_ml
            self.current_peak_pressure_cm_h2o = sample.pressure_cm_h2o
            self.current_etco2_kpa = sample.co2_kpa
            return summary

        self.current_min_volume_ml = min(
            self.current_min_volume_ml,
            sample.volume_ml,
        )
        self.current_max_volume_ml = max(
            self.current_max_volume_ml,
            sample.volume_ml,
        )
        self.current_peak_pressure_cm_h2o = max(
            self.current_peak_pressure_cm_h2o,
            sample.pressure_cm_h2o,
        )
        self.current_etco2_kpa = max(
            self.current_etco2_kpa,
            sample.co2_kpa,
        )
        self.current_latest_time_s = sample.time_s
        return None

    def _finalize_current_breath(self, *, end_time_s: float) -> BreathSummary:
        vt_ml = max(0.0, self.current_max_volume_ml - self.current_min_volume_ml)
        breath_duration_s = max(
            end_time_s - self.current_start_time_s,
            self.minimum_duration_s,
        )
        actual_rr_bpm = 60.0 / breath_duration_s
        minute_volume_l_min = vt_ml * actual_rr_bpm / 1000.0

        self.completed_vt_ml = vt_ml
        self.completed_minute_volume_l_min = minute_volume_l_min
        self.completed_peak_pressure_cm_h2o = self.current_peak_pressure_cm_h2o
        self.completed_etco2_kpa = self.current_etco2_kpa
        self.last_summary = BreathSummary(
            breath=self.current_breath if self.current_breath is not None else 0,
            start_time_s=self.current_start_time_s,
            end_time_s=end_time_s,
            vt_ml=vt_ml,
            minute_volume_l_min=minute_volume_l_min,
            peak_pressure_cm_h2o=self.current_peak_pressure_cm_h2o,
            etco2_kpa=self.current_etco2_kpa,
        )
        return self.last_summary
