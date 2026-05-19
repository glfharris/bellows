"""Waveform widgets for the Textual app."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget

from bellows.waveforms.buffers import TracePoint


@dataclass(frozen=True)
class WaveformSpec:
    title: str
    unit: str
    color: str
    minimum: float
    maximum: float


class WaveformWidget(Widget):
    """Compact rolling trace renderer."""

    DEFAULT_CSS = """
    WaveformWidget {
        height: 1fr;
        min-height: 4;
        padding: 0 1;
    }
    """

    def __init__(self, spec: WaveformSpec, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.spec = spec
        self.points: list[TracePoint] = []
        self.latest: float = 0.0
        self.window_start_s = 0.0
        self.window_end_s = 0.0

    def update_points(
        self,
        points: list[TracePoint],
        *,
        window_start_s: float,
        window_end_s: float,
    ) -> None:
        self.points = points
        self.window_start_s = window_start_s
        self.window_end_s = window_end_s
        if points:
            self.latest = points[-1].value
        self.refresh()

    def render(self) -> RenderableType:
        total_width = max(12, self.size.width - 2)
        scale_width = self._scale_width()
        graph_width = max(8, total_width - scale_width - 1)
        graph_height = max(1, self.size.height - 3)
        rows = self._graph_rows(graph_width, graph_height)

        text = Text()
        label = (
            f"{self.spec.title:<9} "
            f"{self.latest:>5.1f} {self.spec.unit:<6} "
            f"[{self.spec.minimum:g}-{self.spec.maximum:g}]"
        )
        text.append(label[: max(0, self.size.width)], style=f"bold {self.spec.color}")
        text.append("\n")
        for index, row in enumerate(rows):
            text.append(
                self._scale_label(index, graph_height, scale_width),
                style="#4d5a54",
            )
            text.append("│", style="#4d5a54")
            text.append(row, style=self.spec.color)
            text.append("\n")
        for index, axis_row in enumerate(self._axis(graph_width)):
            text.append(" " * scale_width, style="#4d5a54")
            text.append("└" if index == 0 else " ", style="#4d5a54")
            text.append(axis_row, style="#4d5a54")
            if index < 1:
                text.append("\n")
        return text

    def _graph_rows(self, width: int, height: int) -> list[str]:
        if not self.points:
            rows = [[" " for _ in range(width)] for _ in range(height)]
            rows[height // 2] = ["·" for _ in range(width)]
            return ["".join(row) for row in rows]

        sub_width = width * 2
        sub_height = height * 4
        canvas = [[False for _ in range(sub_width)] for _ in range(sub_height)]
        previous: tuple[int, int] | None = None

        for point in self.points:
            mapped = self._map_point(point, sub_width, sub_height)
            if previous is not None:
                self._draw_line(canvas, previous, mapped)
            else:
                x, y = mapped
                canvas[y][x] = True
            previous = mapped

        return self._braille_rows(canvas, width, height)

    def _map_point(
        self,
        point: TracePoint,
        sub_width: int,
        sub_height: int,
    ) -> tuple[int, int]:
        time_range = max(self.window_end_s - self.window_start_s, 0.001)
        x_fraction = (point.time_s - self.window_start_s) / time_range
        x = round(max(0.0, min(1.0, x_fraction)) * (sub_width - 1))

        value_range = max(self.spec.maximum - self.spec.minimum, 0.001)
        y_fraction = (point.value - self.spec.minimum) / value_range
        y_fraction = max(0.0, min(1.0, y_fraction))
        y = round((1.0 - y_fraction) * (sub_height - 1))
        return x, y

    def _draw_line(
        self,
        canvas: list[list[bool]],
        start: tuple[int, int],
        end: tuple[int, int],
    ) -> None:
        x1, y1 = start
        x2, y2 = end
        steps = max(abs(x2 - x1), abs(y2 - y1), 1)

        for step in range(steps + 1):
            fraction = step / steps
            x = round(x1 + (x2 - x1) * fraction)
            y = round(y1 + (y2 - y1) * fraction)
            canvas[y][x] = True

    def _braille_rows(
        self,
        canvas: list[list[bool]],
        width: int,
        height: int,
    ) -> list[str]:
        rows: list[str] = []
        for char_y in range(height):
            line = []
            for char_x in range(width):
                mask = 0
                for sub_y in range(4):
                    for sub_x in range(2):
                        y = char_y * 4 + sub_y
                        x = char_x * 2 + sub_x
                        if canvas[y][x]:
                            mask |= self._braille_bit(sub_x, sub_y)
                line.append(chr(0x2800 + mask) if mask else " ")
            rows.append("".join(line))
        return rows

    def _braille_bit(self, sub_x: int, sub_y: int) -> int:
        bits = {
            (0, 0): 0x01,
            (0, 1): 0x02,
            (0, 2): 0x04,
            (0, 3): 0x40,
            (1, 0): 0x08,
            (1, 1): 0x10,
            (1, 2): 0x20,
            (1, 3): 0x80,
        }
        return bits[(sub_x, sub_y)]

    def _scale_width(self) -> int:
        midpoint = (self.spec.minimum + self.spec.maximum) / 2
        labels = [
            self._format_scale_value(self.spec.maximum),
            self._format_scale_value(midpoint),
            self._format_scale_value(self.spec.minimum),
        ]
        return max(len(label) for label in labels) + 1

    def _scale_label(self, row: int, height: int, width: int) -> str:
        if height <= 1:
            value = (self.spec.minimum + self.spec.maximum) / 2
            return self._format_scale_value(value).rjust(width)

        midpoint_row = height // 2
        if row == 0:
            value = self.spec.maximum
        elif row == midpoint_row:
            value = (self.spec.minimum + self.spec.maximum) / 2
        elif row == height - 1:
            value = self.spec.minimum
        else:
            return " " * width

        return self._format_scale_value(value).rjust(width)

    def _format_scale_value(self, value: float) -> str:
        if abs(value) >= 10 or value == 0:
            return f"{value:.0f}"
        return f"{value:.1f}"

    def _axis(self, width: int) -> list[str]:
        tick_count = 5
        axis = ["─" for _ in range(width)]
        labels = [" " for _ in range(width)]
        duration = max(self.window_end_s - self.window_start_s, 0.0)

        for tick in range(tick_count):
            if tick_count == 1:
                position = 0
                seconds_from_now = 0.0
            else:
                fraction = tick / (tick_count - 1)
                position = round(fraction * (width - 1))
                seconds_from_now = -duration * (1.0 - fraction)

            axis[position] = "┬"
            label = "now" if tick == tick_count - 1 else f"{seconds_from_now:.0f}s"
            label_start = min(max(0, position - len(label) // 2), width - len(label))
            for offset, character in enumerate(label):
                labels[label_start + offset] = character

        return ["".join(axis), "".join(labels)]
