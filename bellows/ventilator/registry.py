"""Ventilator mode registry."""

from __future__ import annotations

from bellows.ventilator.modes.aprv import AirwayPressureReleaseVentilation
from bellows.ventilator.modes.base import VentilatorMode
from bellows.ventilator.modes.pcv import PressureControl
from bellows.ventilator.modes.prvc import PressureRegulatedVolumeControl
from bellows.ventilator.modes.vcv import VolumeControl


VENTILATOR_MODES: tuple[str, ...] = ("VCV", "PCV", "PRVC", "APRV")


def default_modes() -> dict[str, VentilatorMode]:
    return {
        "VCV": VolumeControl(),
        "PCV": PressureControl(),
        "PRVC": PressureRegulatedVolumeControl(),
        "APRV": AirwayPressureReleaseVentilation(),
    }
