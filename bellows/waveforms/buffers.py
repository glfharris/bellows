"""Rolling waveform buffers."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Iterable


@dataclass
class TracePoint:
    time_s: float
    value: float


@dataclass
class TraceBuffer:
    """Timestamped circular buffer for one waveform trace."""

    maxlen: int
    points: Deque[TracePoint] = field(init=False)

    def __post_init__(self) -> None:
        self.points = deque(maxlen=self.maxlen)

    def append(self, time_s: float, value: float) -> None:
        self.points.append(TracePoint(time_s, value))

    def clear(self) -> None:
        self.points.clear()

    def points_since(self, earliest_time_s: float) -> list[TracePoint]:
        return [point for point in self.points if point.time_s >= earliest_time_s]

    def values_since(self, earliest_time_s: float) -> list[float]:
        return [point.value for point in self.points if point.time_s >= earliest_time_s]

    def __iter__(self) -> Iterable[TracePoint]:
        return iter(self.points)
