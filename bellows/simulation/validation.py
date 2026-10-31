"""Shared numeric validation for simulation inputs."""

from math import isfinite


def require_finite(**values: float) -> None:
    for name, value in values.items():
        if not isfinite(value):
            raise ValueError(f"{name} must be finite")
