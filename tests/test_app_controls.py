"""Tests for app control-row behavior."""

from __future__ import annotations

import unittest
from dataclasses import replace

from bellows.app import BellowsApp, CONTROL_DEFINITIONS
from bellows.simulation.lung_model import VenegasHysteresisLung


def _select_control(app: BellowsApp, key: str) -> None:
    for index, row in enumerate(app.control_rows):
        if row.key == key:
            app.selected_control_index = index
            return
    raise AssertionError(f"control row {key!r} not found")


class AppControlTests(unittest.TestCase):
    def test_control_catalog_actions_resolve_to_app_methods(self) -> None:
        app = BellowsApp()

        for definition in CONTROL_DEFINITIONS.values():
            for action in (
                definition.decrease,
                definition.increase,
                definition.activate,
            ):
                if action is None:
                    continue
                with self.subTest(control=definition.key, action=action.method_name):
                    self.assertTrue(callable(getattr(app, action.method_name, None)))

    def test_all_rendered_control_rows_have_catalog_entries(self) -> None:
        app = BellowsApp()

        missing = [
            row.key for row in app.control_rows if row.key not in CONTROL_DEFINITIONS
        ]

        self.assertEqual(missing, [])

    def test_aprv_and_hysteresis_rows_come_from_catalog(self) -> None:
        app = BellowsApp()
        app.simulation.queue_settings(replace(app.simulation.settings, mode="APRV"))
        app.simulation.patient = replace(
            app.simulation.patient,
            lung_model=VenegasHysteresisLung(),
        )

        app._rebuild_control_rows()

        keys = [row.key for row in app.control_rows]
        self.assertIn("p_high", keys)
        self.assertIn("t_low", keys)
        self.assertIn("hysteresis", keys)
        self.assertNotIn("target", keys)
        self.assertNotIn("compliance", keys)

    def test_selected_control_adjust_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "target")

        app._adjust_selected_control(1)

        self.assertIsNotNone(app.simulation.pending_settings)
        self.assertEqual(app.simulation.pending_settings.vt_ml, 525.0)

    def test_selected_waveform_activation_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "co2")

        app.action_activate_selected_control()

        self.assertTrue(app.waveform_visible["co2"])


if __name__ == "__main__":
    unittest.main()
