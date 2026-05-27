"""Collected simulation samples for analysis and export."""

from __future__ import annotations

from collections import deque
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from typing import Any

from bellows.simulation.metrics import BreathSummary
from bellows.simulation.state import SimulationSample


class SimulationRun:
    """A completed collection of simulation samples."""

    samples: tuple[SimulationSample, ...]
    breath_summaries: tuple[BreathSummary, ...]

    def __init__(
        self,
        samples: Iterable[SimulationSample] = (),
        *,
        breath_summaries: Iterable[BreathSummary] = (),
    ) -> None:
        self.samples = tuple(samples)
        self.breath_summaries = tuple(breath_summaries)

    def __iter__(self) -> Iterator[SimulationSample]:
        return iter(self.samples)

    def __len__(self) -> int:
        return len(self.samples)

    def __bool__(self) -> bool:
        return bool(self.samples)

    def __getitem__(self, index: int | slice) -> SimulationSample | SimulationRun:
        if isinstance(index, slice):
            return SimulationRun(
                self.samples[index],
                breath_summaries=self.breath_summaries,
            )
        return self.samples[index]

    def column(self, name: str) -> list[Any]:
        """Return one sample attribute as a list."""

        return [getattr(sample, name) for sample in self.samples]

    def columns(self, *names: str) -> dict[str, list[Any]]:
        """Return multiple sample attributes as column lists."""

        return {name: self.column(name) for name in names}

    @property
    def last_breath_summary(self) -> BreathSummary | None:
        """Return the most recent completed breath summary."""

        if not self.breath_summaries:
            return None
        return self.breath_summaries[-1]

    def breath_summary(self, breath: int = -1) -> BreathSummary | None:
        """Return a completed breath summary by breath number or negative index."""

        if not self.breath_summaries:
            return None
        if breath < 0:
            return self.breath_summaries[breath]
        for summary in self.breath_summaries:
            if summary.breath == breath:
                return summary
        return None

    def summary_column(self, name: str) -> list[Any]:
        """Return one completed-breath summary attribute as a list."""

        return [getattr(summary, name) for summary in self.breath_summaries]

    def summary_columns(self, *names: str) -> dict[str, list[Any]]:
        """Return multiple completed-breath summary attributes as column lists."""

        return {name: self.summary_column(name) for name in names}

    def breath(self, breath: int) -> SimulationRun:
        """Return samples for a breath number, with negative indexes allowed."""

        breath_number = self._resolve_breath_number(breath)
        return SimulationRun(
            (sample for sample in self.samples if sample.breath == breath_number),
            breath_summaries=(
                summary
                for summary in self.breath_summaries
                if summary.breath == breath_number
            ),
        )

    def last_completed_breath(self) -> SimulationRun:
        """Return samples for the last breath with a completed summary."""

        if not self.breath_summaries:
            return SimulationRun()
        return self.breath(self.breath_summaries[-1].breath)

    def _resolve_breath_number(self, breath: int) -> int:
        if breath >= 0:
            return breath

        breath_numbers = sorted({sample.breath for sample in self.samples})
        return breath_numbers[breath]


@dataclass
class SimulationRecorder:
    """Mutable collector for live simulation samples."""

    maxlen: int | None = None
    _samples: deque[SimulationSample] = field(init=False)

    def __post_init__(self) -> None:
        self._samples = deque(maxlen=self.maxlen)

    def append(self, sample: SimulationSample) -> None:
        self._samples.append(sample)

    def extend(self, samples: Iterable[SimulationSample]) -> None:
        self._samples.extend(samples)

    def record(self, samples: Iterable[SimulationSample]) -> list[SimulationSample]:
        """Store samples and return them as a list for immediate consumers."""

        collected = list(samples)
        self.extend(collected)
        return collected

    def clear(self) -> None:
        self._samples.clear()

    def to_run(
        self,
        *,
        breath_summaries: Iterable[BreathSummary] = (),
    ) -> SimulationRun:
        return SimulationRun(self._samples, breath_summaries=breath_summaries)
