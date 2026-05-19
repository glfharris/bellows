"""Lung models — the elastic pressure-volume relationship.

The simulation's airway pressure equation is

    Paw = P_elastic(V, phase) + R * Flow

where ``P_elastic(V)`` is the lung's absolute elastic recoil pressure at
volume ``V``. PEEP is no longer added separately — at end-expiration with
zero flow the ventilator simply holds airway pressure at PEEP, and the
lung settles to whatever volume satisfies ``P_elastic(V_eq) = PEEP``.
This is what lets a recruitable Venegas lung show the recruitment benefit
when PEEP rises: more volume is held at end-expiration, the operating
point climbs onto a better-compliance part of the curve, and less driving
pressure is needed for a given VT.

``LinearLung`` reproduces the original ``V/C`` behaviour with the same
math — it's invariant to the convention. ``VenegasLung`` and
``VenegasHysteresisLung`` use the Venegas sigmoid
``V(P) = a + b/(1 + exp(-(P-c)/d))`` with ``a`` as the lower-asymptote
volume (lung fully empty as ``P -> -inf``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Protocol


PHASE_INSPIRATION = "inspiration"
PHASE_EXPIRATION = "expiration"


class LungModel(Protocol):
    """Phase-aware elastic PV relationship.

    ``elastic_pressure`` returns absolute elastic recoil pressure at the
    given volume. ``elastic_slope`` returns ``dP_elastic/dV`` (i.e.
    ``1 / local compliance``) — used by PRVC's adaptive step.
    ``equilibrium_volume`` is the inverse: the volume at which the lung's
    recoil matches a given holding pressure.
    """

    name: str

    def elastic_pressure(self, volume_l: float, phase: str) -> float:
        ...

    def elastic_slope(self, volume_l: float, phase: str) -> float:
        ...

    def equilibrium_volume(self, pressure_cm_h2o: float, phase: str) -> float:
        ...


@dataclass(frozen=True)
class LinearLung:
    """Constant-compliance lung. ``P_elastic(V) = V / C``."""

    compliance_l_per_cm_h2o: float = 0.05
    name: str = "Linear"

    def elastic_pressure(self, volume_l: float, phase: str) -> float:
        return volume_l / self.compliance_l_per_cm_h2o

    def elastic_slope(self, volume_l: float, phase: str) -> float:
        return 1.0 / self.compliance_l_per_cm_h2o

    def equilibrium_volume(self, pressure_cm_h2o: float, phase: str) -> float:
        return max(0.0, pressure_cm_h2o * self.compliance_l_per_cm_h2o)


@dataclass(frozen=True)
class VenegasLung:
    """Sigmoid PV curve (Venegas 1998).

    Parameters:
      * ``inflection_cm_h2o`` (c): pressure at the curve's inflection.
      * ``slope_width_cm_h2o`` (d): pressure width of the transition.
      * ``recruitable_volume_l`` (b): volume range between lower and
        upper asymptotes.
      * ``residual_volume_l`` (a): lower-asymptote volume — what the lung
        holds at very negative pressure. Default 0 corresponds to a fully
        collapsible lung; real lungs have a positive RV but for the
        purposes of this educational model 0 keeps the numbers simple.
    """

    inflection_cm_h2o: float = 18.0
    slope_width_cm_h2o: float = 5.0
    recruitable_volume_l: float = 1.2
    residual_volume_l: float = 0.0
    name: str = "Venegas"

    def elastic_pressure(self, volume_l: float, phase: str) -> float:
        return _venegas_pressure(
            volume_l,
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.inflection_cm_h2o,
            self.slope_width_cm_h2o,
        )

    def elastic_slope(self, volume_l: float, phase: str) -> float:
        return _venegas_slope(
            volume_l,
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.slope_width_cm_h2o,
        )

    def equilibrium_volume(self, pressure_cm_h2o: float, phase: str) -> float:
        return _venegas_volume(
            pressure_cm_h2o,
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.inflection_cm_h2o,
            self.slope_width_cm_h2o,
        )


@dataclass(frozen=True)
class VenegasHysteresisLung:
    """Venegas sigmoid with inflation/deflation hysteresis.

    Modelled as a single sigmoid shifted by ``+hysteresis_offset/2`` on
    inspiration and ``-hysteresis_offset/2`` on expiration. The deflation
    limb therefore sits to the left of (and below) the inflation limb in
    the PV plane.
    """

    inflection_cm_h2o: float = 18.0
    slope_width_cm_h2o: float = 5.0
    recruitable_volume_l: float = 1.2
    residual_volume_l: float = 0.0
    hysteresis_offset_cm_h2o: float = 3.0
    name: str = "Venegas+H"

    def _shift(self, phase: str) -> float:
        half = self.hysteresis_offset_cm_h2o / 2.0
        return -half if phase == PHASE_EXPIRATION else half

    def elastic_pressure(self, volume_l: float, phase: str) -> float:
        base = _venegas_pressure(
            volume_l,
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.inflection_cm_h2o,
            self.slope_width_cm_h2o,
        )
        return base + self._shift(phase)

    def elastic_slope(self, volume_l: float, phase: str) -> float:
        # Slope is independent of the vertical shift.
        return _venegas_slope(
            volume_l,
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.slope_width_cm_h2o,
        )

    def equilibrium_volume(self, pressure_cm_h2o: float, phase: str) -> float:
        return _venegas_volume(
            pressure_cm_h2o - self._shift(phase),
            self.residual_volume_l,
            self.recruitable_volume_l,
            self.inflection_cm_h2o,
            self.slope_width_cm_h2o,
        )


def _venegas_pressure(
    volume_l: float,
    a_l: float,
    b_l: float,
    c_cm_h2o: float,
    d_cm_h2o: float,
) -> float:
    # Inverse of V = a + b / (1 + exp(-(P-c)/d))
    # P = c - d * ln(b/(V-a) - 1)
    frac = (volume_l - a_l) / b_l
    frac = max(1e-4, min(1.0 - 1e-4, frac))
    return c_cm_h2o - d_cm_h2o * math.log(1.0 / frac - 1.0)


def _venegas_slope(
    volume_l: float,
    a_l: float,
    b_l: float,
    d_cm_h2o: float,
) -> float:
    # Local compliance C_local = dV/dP = (b/d) * frac * (1 - frac).
    # Slope = dP/dV = 1 / C_local.
    frac = (volume_l - a_l) / b_l
    frac = max(1e-4, min(1.0 - 1e-4, frac))
    local_c = (b_l / d_cm_h2o) * frac * (1.0 - frac)
    return 1.0 / max(local_c, 1e-3)


def _venegas_volume(
    pressure_cm_h2o: float,
    a_l: float,
    b_l: float,
    c_cm_h2o: float,
    d_cm_h2o: float,
) -> float:
    # V = a + b / (1 + exp(-(P-c)/d))
    exponent = -(pressure_cm_h2o - c_cm_h2o) / d_cm_h2o
    # Clamp to avoid overflow at extreme negative pressures.
    exponent = max(-50.0, min(50.0, exponent))
    return a_l + b_l / (1.0 + math.exp(exponent))
