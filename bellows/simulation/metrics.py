"""Breath-level summaries and history."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable
from dataclasses import dataclass, field

from bellows.simulation.state import SimulationSample


@dataclass(frozen=True)
class BreathSummary:
    """Facts about one completed breath."""

    breath: int
    start_time_s: float
    end_time_s: float
    min_volume_l: float
    max_volume_l: float
    peak_pressure_cm_h2o: float
    etco2_kpa: float

    @property
    def duration_s(self) -> float:
        return max(0.0, self.end_time_s - self.start_time_s)

    @property
    def delivered_vt_l(self) -> float:
        return max(0.0, self.max_volume_l - self.min_volume_l)

    @property
    def vt_ml(self) -> float:
        return self.delivered_vt_l * 1000.0

    @property
    def peak_volume_l(self) -> float:
        return self.max_volume_l

    @property
    def minute_volume_l_min(self) -> float:
        duration_s = max(self.duration_s, 0.01)
        return self.delivered_vt_l * 60.0 / duration_s


@dataclass
class BreathAccumulator:
    """Accumulate samples for the current breath and finalize a summary."""

    current_breath: int | None = None
    current_start_time_s: float = 0.0
    current_min_volume_l: float = 0.0
    current_max_volume_l: float = 0.0
    current_peak_pressure_cm_h2o: float = 0.0
    current_etco2_kpa: float = 0.0

    def observe(self, sample: SimulationSample) -> None:
        volume_l = sample.volume_ml / 1000.0
        if self.current_breath is None:
            self.current_breath = sample.breath
            self.current_start_time_s = sample.time_s
            self.current_min_volume_l = volume_l
            self.current_max_volume_l = volume_l
            self.current_peak_pressure_cm_h2o = sample.pressure_cm_h2o
            self.current_etco2_kpa = sample.co2_kpa
            return

        self.current_min_volume_l = min(self.current_min_volume_l, volume_l)
        self.current_max_volume_l = max(self.current_max_volume_l, volume_l)
        self.current_peak_pressure_cm_h2o = max(
            self.current_peak_pressure_cm_h2o,
            sample.pressure_cm_h2o,
        )
        self.current_etco2_kpa = max(self.current_etco2_kpa, sample.co2_kpa)

    def finish(self, *, end_time_s: float) -> BreathSummary | None:
        if self.current_breath is None:
            return None

        summary = BreathSummary(
            breath=self.current_breath,
            start_time_s=self.current_start_time_s,
            end_time_s=end_time_s,
            min_volume_l=self.current_min_volume_l,
            max_volume_l=self.current_max_volume_l,
            peak_pressure_cm_h2o=self.current_peak_pressure_cm_h2o,
            etco2_kpa=self.current_etco2_kpa,
        )
        self.clear()
        return summary

    def clear(self) -> None:
        self.current_breath = None
        self.current_start_time_s = 0.0
        self.current_min_volume_l = 0.0
        self.current_max_volume_l = 0.0
        self.current_peak_pressure_cm_h2o = 0.0
        self.current_etco2_kpa = 0.0


@dataclass
class BreathHistory:
    """Bounded collection of completed breath summaries."""

    maxlen: int = 200
    _breaths: deque[BreathSummary] = field(init=False)

    def __post_init__(self) -> None:
        self._breaths = deque(maxlen=self.maxlen)

    def append(self, summary: BreathSummary) -> None:
        self._breaths.append(summary)

    @property
    def last(self) -> BreathSummary | None:
        if not self._breaths:
            return None
        return self._breaths[-1]

    def recent(self, count: int) -> list[BreathSummary]:
        if count <= 0:
            return []
        return list(self._breaths)[-count:]

    def since(self, time_s: float) -> list[BreathSummary]:
        return [breath for breath in self._breaths if breath.end_time_s >= time_s]

    def clear(self) -> None:
        self._breaths.clear()

    def __iter__(self) -> Iterable[BreathSummary]:
        return iter(self._breaths)

    def __len__(self) -> int:
        return len(self._breaths)
