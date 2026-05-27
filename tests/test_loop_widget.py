"""Tests for loop rendering geometry and breath selection."""

from __future__ import annotations

import unittest

from bellows.simulation.phase import PHASE_EXPIRATION, PHASE_INSPIRATION
from bellows.ui.loop import LoopPoint, LoopSpec, LoopWidget, loop_points_by_breath


class LoopWidgetTests(unittest.TestCase):
    def test_scale_width_is_stable(self) -> None:
        loop = LoopWidget(_spec())

        self.assertEqual(loop._scale_width(), LoopWidget.SCALE_WIDTH)

    def test_map_point_clamps_to_plot_bounds(self) -> None:
        loop = LoopWidget(_spec())
        canvas = loop._empty_canvas(10, 5)

        low = loop._map_point(
            LoopPoint(0, -100.0, -20.0, PHASE_INSPIRATION),
            canvas,
        )
        high = loop._map_point(
            LoopPoint(0, 1200.0, 80.0, PHASE_EXPIRATION),
            canvas,
        )

        self.assertEqual(low, (0, 19))
        self.assertEqual(high, (19, 0))

    def test_loop_points_by_breath_returns_current_and_nearest_previous(self) -> None:
        points = [
            LoopPoint(0, 100.0, 5.0, PHASE_INSPIRATION),
            LoopPoint(1, 120.0, 6.0, PHASE_INSPIRATION),
            LoopPoint(1, 180.0, 10.0, PHASE_EXPIRATION),
            LoopPoint(2, 130.0, 7.0, PHASE_INSPIRATION),
        ]

        current, previous = loop_points_by_breath(points, 2)

        self.assertEqual([point.breath for point in current], [2])
        self.assertEqual([point.breath for point in previous], [1, 1])


def _spec() -> LoopSpec:
    return LoopSpec(
        "PV Loop",
        "mL",
        "cmH2O",
        0.0,
        1000.0,
        0.0,
        50.0,
        "#f5c451",
        "#9b7c35",
    )


if __name__ == "__main__":
    unittest.main()
