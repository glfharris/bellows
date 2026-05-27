"""Loop widgets for pressure-volume and related plots."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from rich.console import RenderableType
from rich.text import Text
from textual.widget import Widget

from bellows.simulation.phase import PHASE_INSPIRATION


@dataclass(frozen=True)
class LoopPoint:
    breath: int
    x: float
    y: float
    phase: str


@dataclass(frozen=True)
class LoopSpec:
    title: str
    x_unit: str
    y_unit: str
    x_minimum: float
    x_maximum: float
    y_minimum: float
    y_maximum: float
    inspiration_color: str
    expiration_color: str
    previous_color: str = "#4d5a54"


class LoopWidget(Widget):
    """Compact x/y loop renderer with current and previous breath traces."""

    SCALE_WIDTH = 6

    DEFAULT_CSS = """
    LoopWidget {
        height: 1fr;
        min-height: 6;
        padding: 0 1;
    }
    """

    def __init__(self, spec: LoopSpec, *, id: str | None = None) -> None:
        super().__init__(id=id)
        self.spec = spec
        self.current_points: list[LoopPoint] = []
        self.previous_points: list[LoopPoint] = []
        self.latest_x = 0.0
        self.latest_y = 0.0

    def update_points(
        self,
        current_points: list[LoopPoint],
        previous_points: list[LoopPoint],
    ) -> None:
        self.current_points = current_points
        self.previous_points = previous_points
        if current_points:
            latest = current_points[-1]
            self.latest_x = latest.x
            self.latest_y = latest.y
        elif previous_points:
            latest = previous_points[-1]
            self.latest_x = latest.x
            self.latest_y = latest.y
        self.refresh()

    def render(self) -> RenderableType:
        total_width = max(12, self.size.width - 2)
        scale_width = self._scale_width()
        graph_width = max(8, total_width - scale_width - 1)
        graph_height = max(1, self.size.height - 3)

        previous_canvas = self._empty_canvas(graph_width, graph_height)
        inspiration_canvas = self._empty_canvas(graph_width, graph_height)
        expiration_canvas = self._empty_canvas(graph_width, graph_height)
        self._draw_points(previous_canvas, self.previous_points)
        self._draw_phase_points(inspiration_canvas, expiration_canvas)

        text = Text()
        label = (
            f"{self.spec.title:<9} "
            f"{self.latest_x:>5.0f} {self.spec.x_unit}  "
            f"{self.latest_y:>5.1f} {self.spec.y_unit} "
            f"[{self.spec.x_minimum:g}-{self.spec.x_maximum:g} "
            f"{self.spec.x_unit}]"
        )
        text.append(
            label[: max(0, self.size.width)],
            style=f"bold {self.spec.inspiration_color}",
        )
        text.append("\n")

        for row in range(graph_height):
            text.append(
                self._scale_label(row, graph_height, scale_width),
                style="#4d5a54",
            )
            text.append("│", style="#4d5a54")
            self._append_loop_row(
                text,
                previous_canvas,
                inspiration_canvas,
                expiration_canvas,
                row,
                graph_width,
            )
            text.append("\n")

        for index, axis_row in enumerate(self._axis(graph_width)):
            text.append(" " * scale_width, style="#4d5a54")
            text.append("└" if index == 0 else " ", style="#4d5a54")
            text.append(axis_row, style="#4d5a54")
            if index < 1:
                text.append("\n")
        return text

    def _draw_phase_points(
        self,
        inspiration_canvas: list[list[bool]],
        expiration_canvas: list[list[bool]],
    ) -> None:
        if not self.current_points:
            return

        previous = self._map_point(self.current_points[0], inspiration_canvas)
        target_canvas = (
            inspiration_canvas
            if self.current_points[0].phase == PHASE_INSPIRATION
            else expiration_canvas
        )
        x, y = previous
        target_canvas[y][x] = True

        for point in self.current_points[1:]:
            mapped = self._map_point(point, inspiration_canvas)
            target_canvas = (
                inspiration_canvas
                if point.phase == PHASE_INSPIRATION
                else expiration_canvas
            )
            self._draw_line(target_canvas, previous, mapped)
            previous = mapped

    def _draw_points(
        self,
        canvas: list[list[bool]],
        points: list[LoopPoint],
    ) -> None:
        previous: tuple[int, int] | None = None
        for point in points:
            mapped = self._map_point(point, canvas)
            if previous is None:
                x, y = mapped
                canvas[y][x] = True
            else:
                self._draw_line(canvas, previous, mapped)
            previous = mapped

    def _empty_canvas(self, width: int, height: int) -> list[list[bool]]:
        return [[False for _ in range(width * 2)] for _ in range(height * 4)]

    def _map_point(
        self,
        point: LoopPoint,
        canvas: list[list[bool]],
    ) -> tuple[int, int]:
        sub_height = len(canvas)
        sub_width = len(canvas[0])
        x_range = max(self.spec.x_maximum - self.spec.x_minimum, 0.001)
        y_range = max(self.spec.y_maximum - self.spec.y_minimum, 0.001)

        x_fraction = (point.x - self.spec.x_minimum) / x_range
        y_fraction = (point.y - self.spec.y_minimum) / y_range
        x = round(max(0.0, min(1.0, x_fraction)) * (sub_width - 1))
        y = round((1.0 - max(0.0, min(1.0, y_fraction))) * (sub_height - 1))
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

    def _append_loop_row(
        self,
        text: Text,
        previous_canvas: list[list[bool]],
        inspiration_canvas: list[list[bool]],
        expiration_canvas: list[list[bool]],
        row: int,
        width: int,
    ) -> None:
        for column in range(width):
            inspiration_mask = self._cell_mask(inspiration_canvas, column, row)
            expiration_mask = self._cell_mask(expiration_canvas, column, row)
            previous_mask = self._cell_mask(previous_canvas, column, row)

            if inspiration_mask:
                text.append(chr(0x2800 + inspiration_mask), self.spec.inspiration_color)
            elif expiration_mask:
                text.append(chr(0x2800 + expiration_mask), self.spec.expiration_color)
            elif previous_mask:
                text.append(chr(0x2800 + previous_mask), self.spec.previous_color)
            else:
                text.append(" ")

    def _cell_mask(self, canvas: list[list[bool]], char_x: int, char_y: int) -> int:
        mask = 0
        for sub_y in range(4):
            for sub_x in range(2):
                y = char_y * 4 + sub_y
                x = char_x * 2 + sub_x
                if canvas[y][x]:
                    mask |= self._braille_bit(sub_x, sub_y)
        return mask

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
        return self.SCALE_WIDTH

    def _scale_label(self, row: int, height: int, width: int) -> str:
        if height <= 1:
            value = (self.spec.y_minimum + self.spec.y_maximum) / 2
            return self._format_scale_value(value).rjust(width)

        midpoint_row = height // 2
        if row == 0:
            value = self.spec.y_maximum
        elif row == midpoint_row:
            value = (self.spec.y_minimum + self.spec.y_maximum) / 2
        elif row == height - 1:
            value = self.spec.y_minimum
        else:
            return " " * width
        return self._format_scale_value(value).rjust(width)

    def _axis(self, width: int) -> list[str]:
        tick_count = 3
        axis = ["─" for _ in range(width)]
        labels = [" " for _ in range(width)]

        for tick in range(tick_count):
            fraction = tick / (tick_count - 1)
            position = round(fraction * (width - 1))
            value = self.spec.x_minimum + (
                self.spec.x_maximum - self.spec.x_minimum
            ) * fraction
            axis[position] = "┬"
            label = self._format_scale_value(value)
            label_start = min(max(0, position - len(label) // 2), width - len(label))
            for offset, character in enumerate(label):
                labels[label_start + offset] = character

        return ["".join(axis), "".join(labels)]

    def _format_scale_value(self, value: float) -> str:
        if abs(value) >= 10 or value == 0:
            return f"{value:.0f}"
        return f"{value:.1f}"


def loop_points_by_breath(
    points: list[LoopPoint],
    current_breath: int,
) -> tuple[list[LoopPoint], list[LoopPoint]]:
    """Return current and nearest previous breath points."""

    current = [point for point in points if point.breath == current_breath]
    by_breath: dict[int, list[LoopPoint]] = defaultdict(list)
    for point in points:
        if point.breath < current_breath:
            by_breath[point.breath].append(point)

    if not by_breath:
        return current, []
    previous_breath = max(by_breath)
    return current, by_breath[previous_breath]
