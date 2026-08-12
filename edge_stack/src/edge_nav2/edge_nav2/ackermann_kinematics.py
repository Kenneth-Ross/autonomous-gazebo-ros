"""Ackermann bicycle-model conversion helpers."""

import math


def bounded_yaw_rate(
    linear_velocity, yaw_rate, wheelbase, max_steering_angle, min_velocity=0.1,
):
    """Limit moving yaw rate to what front steering can physically produce."""
    if wheelbase <= 0.0:
        raise ValueError('wheelbase must be positive')
    if max_steering_angle <= 0.0:
        raise ValueError('max_steering_angle must be positive')
    if abs(linear_velocity) < min_velocity:
        return yaw_rate
    limit = abs(linear_velocity) * math.tan(max_steering_angle) / wheelbase
    return max(-limit, min(limit, yaw_rate))


def steering_angle(
    velocity,
    angular_velocity,
    wheelbase,
    min_velocity,
    max_steering_angle,
):
    """Convert yaw-rate intent to a bounded physical steering angle."""
    if wheelbase <= 0.0 or min_velocity <= 0.0:
        raise ValueError('wheelbase and min_velocity must be positive')
    if max_steering_angle <= 0.0:
        raise ValueError('max_steering_angle must be positive')
    effective_velocity = max(abs(velocity), min_velocity)
    angle = math.atan(wheelbase * angular_velocity / effective_velocity)
    return max(-max_steering_angle, min(max_steering_angle, angle))
