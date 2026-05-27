"""Tests for command-line parsing."""

from __future__ import annotations

import contextlib
import io
import unittest

from bellows.cli import parse_args


class CliParsingTests(unittest.TestCase):
    def test_defaults_to_tui_when_no_command_is_given(self) -> None:
        args, _parser = parse_args(
            [
                "--mode",
                "PRVC",
                "--vt",
                "450",
                "--exp-valve-resistance",
                "4",
                "--rise-time",
                "0.06",
            ]
        )

        self.assertEqual(args.command, "tui")
        self.assertEqual(args.mode, "PRVC")
        self.assertEqual(args.vt, 450.0)
        self.assertEqual(args.exp_valve_resistance, 4.0)
        self.assertEqual(args.rise_time, 0.06)

    def test_accepts_explicit_tui_command(self) -> None:
        args, _parser = parse_args(
            ["tui", "--mode", "pcv", "--peep", "8", "--lung-model", "venegas"]
        )

        self.assertEqual(args.command, "tui")
        self.assertEqual(args.mode, "PCV")
        self.assertEqual(args.peep, 8.0)
        self.assertEqual(args.lung_model, "Venegas")

    def test_accepts_web_command(self) -> None:
        args, _parser = parse_args(
            ["web", "--host", "localhost", "--port", "8888", "--mode", "pcv"]
        )

        self.assertEqual(args.command, "web")
        self.assertEqual(args.host, "localhost")
        self.assertEqual(args.port, 8888)
        self.assertEqual(args.mode, "PCV")

    def test_rejects_unknown_command(self) -> None:
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                parse_args(["generate", "--mode", "VCV"])


if __name__ == "__main__":
    unittest.main()
