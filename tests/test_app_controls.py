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


def _advance_until_pending_settings_apply(app: BellowsApp) -> None:
    for _ in range(500):
        if app.simulation.pending_settings is None:
            return
        app._tick()
    raise AssertionError("pending settings were not applied")


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
        app.simulation.settings = replace(app.simulation.settings, mode="APRV")
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

    def test_ventilator_rows_use_mode_control_keys(self) -> None:
        app = BellowsApp()
        app.simulation.settings = replace(app.simulation.settings, mode="APRV")
        app._rebuild_control_rows()

        mode = app.simulation.mode_for("APRV")
        keys = [row.key for row in app.control_rows]

        for key in mode.control_keys:
            self.assertIn(key, keys)
        self.assertNotIn("target", keys)

    def test_pending_mode_change_keeps_active_mode_controls_visible(self) -> None:
        app = BellowsApp()
        app.simulation.queue_settings(replace(app.simulation.settings, mode="APRV"))
        app._rebuild_control_rows()

        keys = [row.key for row in app.control_rows]

        self.assertIn("target", keys)
        self.assertIn("rr", keys)
        self.assertNotIn("p_high", keys)

    def test_pending_mode_change_blocks_active_control_adjustment(self) -> None:
        app = BellowsApp()
        app.simulation.queue_settings(replace(app.simulation.settings, mode="APRV"))
        _select_control(app, "target")

        app._adjust_selected_control(1)

        self.assertEqual(app.simulation.pending_settings.mode, "APRV")
        self.assertEqual(app.simulation.pending_settings.vt_ml, 500.0)
        self.assertEqual(app.message, "Mode change pending; wait for next breath")

    def test_pending_mode_change_blocks_direct_setting_shortcut(self) -> None:
        app = BellowsApp()
        app.simulation.queue_settings(replace(app.simulation.settings, mode="APRV"))

        app.action_target_up()

        self.assertEqual(app.simulation.pending_settings.mode, "APRV")
        self.assertEqual(app.simulation.pending_settings.vt_ml, 500.0)
        self.assertEqual(app.message, "Mode change pending; wait for next breath")

    def test_aprv_rows_are_selectable_after_pending_mode_applies(self) -> None:
        app = BellowsApp()
        app._set_settings(replace(app.simulation.settings, mode="APRV"), "Mode APRV")

        _advance_until_pending_settings_apply(app)
        app.action_select_next_control()
        app.action_select_next_control()
        app.action_select_next_control()

        self.assertEqual(app.simulation.settings.mode, "APRV")
        self.assertIn("p_high", [row.key for row in app.control_rows])
        self.assertNotIn("target", [row.key for row in app.control_rows])
        self.assertEqual(app._selected_control_key(), "p_high")

    def test_mode_specific_target_label_is_used_for_rows(self) -> None:
        app = BellowsApp()
        app.simulation.settings = replace(app.simulation.settings, mode="PCV")

        rows = app._ventilator_rows(
            app.simulation.mode_for("PCV"),
            app.simulation.settings,
            None,
        )

        self.assertTrue(rows[0].startswith("  Pinsp"))

    def test_selected_control_adjust_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "target")

        app._adjust_selected_control(1)

        self.assertIsNotNone(app.simulation.pending_settings)
        self.assertEqual(app.simulation.pending_settings.vt_ml, 525.0)

    def test_expiratory_valve_adjust_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "exp_valve")

        app._adjust_selected_control(1)

        self.assertIsNotNone(app.simulation.pending_settings)
        self.assertEqual(
            app.simulation.pending_settings.expiratory_valve_resistance_cm_h2o_s_per_l,
            4.0,
        )

    def test_rise_time_adjust_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "rise_time")

        app._adjust_selected_control(1)

        self.assertIsNotNone(app.simulation.pending_settings)
        self.assertAlmostEqual(
            app.simulation.pending_settings.pressure_rise_time_s,
            0.09,
        )

    def test_selected_waveform_activation_uses_catalog_action(self) -> None:
        app = BellowsApp()
        _select_control(app, "co2")

        app.action_activate_selected_control()

        self.assertTrue(app.waveform_visible["co2"])

    def test_pv_loop_is_toggled_by_keybinding_action(self) -> None:
        app = BellowsApp()

        app.action_toggle_pv_loop()

        self.assertFalse(app.waveform_visible["pv_loop"])

    def test_pv_loop_is_not_a_control_row(self) -> None:
        app = BellowsApp()

        self.assertNotIn("pv_loop", [row.key for row in app.control_rows])

    def test_app_starts_with_initial_sample_in_traces(self) -> None:
        app = BellowsApp()

        initial = app.simulation.current_sample()

        self.assertEqual(app.buffers["pressure"].points[0].time_s, 0.0)
        self.assertEqual(
            app.buffers["pressure"].points[0].value,
            initial.pressure_cm_h2o,
        )
        self.assertEqual(app.loop_points[0].x, initial.volume_ml)
        self.assertEqual(app.recorded_run()[0], initial)

    def test_reset_restores_initial_sample_in_traces(self) -> None:
        app = BellowsApp()
        app._tick()

        app.action_reset()

        initial = app.simulation.current_sample()
        self.assertEqual(len(app.recorded_run()), 1)
        self.assertEqual(len(app.buffers["pressure"].points), 1)
        self.assertEqual(app.buffers["pressure"].points[0].time_s, 0.0)
        self.assertEqual(
            app.buffers["pressure"].points[0].value,
            initial.pressure_cm_h2o,
        )

    def test_tick_collects_pressure_volume_loop_points(self) -> None:
        app = BellowsApp()

        app._tick()

        self.assertGreater(len(app.loop_points), 0)
        self.assertGreater(len(app.recorded_run()), 0)
        point = app.loop_points[-1]
        self.assertEqual(point.breath, app.simulation.breath)
        self.assertGreaterEqual(point.x, 0.0)
        self.assertGreaterEqual(point.y, 0.0)


if __name__ == "__main__":
    unittest.main()
