"""Command-line interface for Bellows."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from bellows.app import BellowsApp
from bellows.config import build_simulation_config
from bellows.simulation.presets import LUNG_MODELS
from bellows.ventilator.registry import VENTILATOR_MODES


COMMANDS = ("tui",)


def main(argv: Sequence[str] | None = None) -> None:
    args, parser = parse_args(argv)

    try:
        config = build_simulation_config(
            mode=args.mode,
            vt_ml=args.vt,
            rr_bpm=args.rr,
            pinsp_cm_h2o=args.pinsp,
            peep_cm_h2o=args.peep,
            ie=args.ie,
            p_high_cm_h2o=args.p_high,
            p_low_cm_h2o=args.p_low,
            t_high_s=args.t_high,
            t_low_s=args.t_low,
            expiratory_valve_resistance_cm_h2o_s_per_l=args.exp_valve_resistance,
            pressure_rise_time_s=args.rise_time,
            lung_model=args.lung_model,
            preset=args.preset,
        )
    except ValueError as exc:
        parser.error(str(exc))

    BellowsApp(
        simulation=config.build_simulation(),
        patient_preset_name=config.patient_preset_name,
    ).run()


def parse_args(
    argv: Sequence[str] | None = None,
) -> tuple[argparse.Namespace, argparse.ArgumentParser]:
    """Parse CLI arguments.

    ``bellows`` defaults to the TUI command, so startup flags work both as
    ``bellows --mode PRVC`` and ``bellows tui --mode PRVC``.
    """

    raw_args = list(sys.argv[1:] if argv is None else argv)
    prog = "bellows"

    if raw_args and raw_args[0] in COMMANDS:
        command = raw_args.pop(0)
        prog = f"{prog} {command}"
    elif raw_args and not raw_args[0].startswith("-"):
        parser = _build_root_parser()
        parser.error(
            f"unknown command {raw_args[0]!r}; choose one of {', '.join(COMMANDS)}"
        )

    parser = _build_tui_parser(prog=prog)
    args = parser.parse_args(raw_args)
    args.command = "tui"
    return args, parser


def _build_root_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="bellows",
        description="Terminal ventilation simulator.",
    )
    parser.add_argument(
        "command",
        nargs="?",
        choices=COMMANDS,
        help="Command to run. Defaults to tui.",
    )
    return parser


def _build_tui_parser(*, prog: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=prog,
        description="Run the interactive Bellows ventilator simulator.",
    )
    _add_startup_options(parser)
    return parser


def _add_startup_options(parser: argparse.ArgumentParser) -> None:
    ventilator = parser.add_argument_group("ventilator startup options")
    ventilator.add_argument(
        "--mode",
        choices=VENTILATOR_MODES,
        type=str.upper,
        help="Ventilator mode.",
    )
    ventilator.add_argument("--vt", type=float, metavar="ML", help="Tidal volume.")
    ventilator.add_argument(
        "--rr",
        type=float,
        metavar="BPM",
        help="Respiratory rate.",
    )
    ventilator.add_argument(
        "--pinsp",
        type=float,
        metavar="CMH2O",
        help="Inspiratory pressure above PEEP for PCV/PRVC-shaped breaths.",
    )
    ventilator.add_argument("--peep", type=float, metavar="CMH2O", help="PEEP.")
    ventilator.add_argument(
        "--ie",
        metavar="I:E",
        help="Inspiratory:expiratory ratio, for example 1:2.",
    )
    ventilator.add_argument(
        "--p-high",
        type=float,
        metavar="CMH2O",
        help="APRV high pressure.",
    )
    ventilator.add_argument(
        "--p-low",
        type=float,
        metavar="CMH2O",
        help="APRV low pressure.",
    )
    ventilator.add_argument(
        "--t-high",
        type=float,
        metavar="S",
        help="APRV high time.",
    )
    ventilator.add_argument("--t-low", type=float, metavar="S", help="APRV low time.")
    ventilator.add_argument(
        "--exp-valve-resistance",
        type=float,
        metavar="CMH2O*S/L",
        help="Expiratory valve resistance.",
    )
    ventilator.add_argument(
        "--rise-time",
        type=float,
        metavar="S",
        help="Pressure-target rise time to about 95% of target.",
    )

    patient = parser.add_argument_group("patient startup options")
    patient.add_argument(
        "--lung-model",
        choices=LUNG_MODELS,
        type=_lung_model_name,
        help="Patient lung model.",
    )
    patient.add_argument(
        "--preset",
        help="Patient preset name for the selected lung model.",
    )


def _lung_model_name(value: str) -> str:
    for choice in LUNG_MODELS:
        if choice.casefold() == value.casefold():
            return choice
    return value


if __name__ == "__main__":
    main()
