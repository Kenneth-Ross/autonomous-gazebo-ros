"""Deterministic low-level safety and actuator control helpers."""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class WatchdogState:
    """Control state after evaluating command freshness."""

    triggered: bool
    throttle: float
    brake: float
    target_velocity: float
    target_steering: float
    velocity_error_sum: float


def apply_watchdog(
    command_age,
    timeout,
    throttle,
    brake,
    target_velocity,
    target_steering,
    velocity_error_sum,
):
    """Return a fail-safe state once command age reaches the deadline."""
    if command_age < timeout:
        return WatchdogState(
            False, throttle, brake, target_velocity, target_steering,
            velocity_error_sum,
        )
    return WatchdogState(True, 0.0, 1.0, 0.0, 0.0, 0.0)


def slew_steering(current, target, slew_rate, max_steering_angle, dt):
    """Move a normalized steering input at a physical radian/second limit."""
    if max_steering_angle <= 0.0:
        raise ValueError('max_steering_angle must be positive')
    if slew_rate < 0.0 or dt < 0.0:
        raise ValueError('slew_rate and dt must be non-negative')
    difference = target - current
    max_change = (slew_rate / max_steering_angle) * dt
    if abs(difference) <= max_change:
        return target
    return current + math.copysign(max_change, difference)


def is_manual_override_active(age, timeout):
    """Return whether the exclusive manual-control window is active."""
    return 0.0 <= age < timeout
