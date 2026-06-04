"""Tests for waveform rendering geometry."""

from __future__ import annotations

import unittest

from bellows.ui.waveform import WaveformSpec, WaveformWidget
from bellows.waveforms.buffers import TracePoint


class WaveformWidgetTests(unittest.TestCase):
    def test_scale_width_is_stable_across_different_axis_labels(self) -> None:
        pressure = WaveformWidget(
            WaveformSpec("Pressure", "cmH2O", "#f5c451", 0.0, 60.0)
        )
        flow = WaveformWidget(
            WaveformSpec("Flow", "L/min", "#57c7ff", -180.0, 80.0)
        )
        volume = WaveformWidget(
            WaveformSpec("Volume", "mL", "#72d572", 0.0, 1500.0)
        )
        co2 = WaveformWidget(WaveformSpec("CO2", "kPa", "#d78cff", 0.0, 7.0))

        widths = {
            pressure._scale_width(),
            flow._scale_width(),
            volume._scale_width(),
            co2._scale_width(),
        }

        self.assertEqual(widths, {WaveformWidget.SCALE_WIDTH})

    def test_display_points_keep_one_value_per_terminal_subcolumn(self) -> None:
        widget = WaveformWidget(
            WaveformSpec("Flow", "L/min", "#57c7ff", -100.0, 100.0)
        )
        widget.update_points(
            [
                TracePoint(0.00, 80.0),
                TracePoint(0.01, -80.0),
                TracePoint(1.00, 0.0),
            ],
            window_start_s=-1.0,
            window_end_s=9.0,
        )

        display_points = widget._display_points(sub_width=20, sub_height=20)

        self.assertEqual(display_points, [(0, 17), (2, 10)])

    def test_sweep_display_breaks_segments_at_wraparound(self) -> None:
        widget = WaveformWidget(
            WaveformSpec("Pressure", "cmH2O", "#f5c451", 0.0, 40.0)
        )
        widget.update_points(
            [
                TracePoint(8.0, 10.0),
                TracePoint(9.0, 20.0),
                TracePoint(10.1, 30.0),
                TracePoint(10.2, 25.0),
            ],
            window_start_s=-5.0,
            window_end_s=5.0,
        )

        segments = widget._display_segments(sub_width=20, sub_height=20)

        self.assertEqual(len(segments), 2)
        self.assertGreater(segments[0][-1][0], segments[1][0][0])

    def test_sweep_display_blanks_gap_at_write_head(self) -> None:
        widget = WaveformWidget(
            WaveformSpec("Pressure", "cmH2O", "#f5c451", 0.0, 40.0)
        )
        widget.update_points(
            [
                TracePoint(4.8, 10.0),
                TracePoint(5.0, 20.0),
                TracePoint(5.2, 30.0),
                TracePoint(6.0, 25.0),
            ],
            window_start_s=-5.0,
            window_end_s=5.0,
        )

        display_points = widget._display_points(sub_width=40, sub_height=20)
        cursor_x = widget._cursor_x(40)

        self.assertTrue(display_points)
        self.assertTrue(
            all(abs(x - cursor_x) > 1 for x, _y in display_points),
        )


if __name__ == "__main__":
    unittest.main()
