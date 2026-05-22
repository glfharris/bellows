"""Tests for waveform rendering geometry."""

from __future__ import annotations

import unittest

from bellows.ui.waveform import WaveformSpec, WaveformWidget


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


if __name__ == "__main__":
    unittest.main()
