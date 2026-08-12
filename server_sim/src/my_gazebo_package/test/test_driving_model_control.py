import math

import pytest

from my_gazebo_package_py.driving_model_control import (
    apply_watchdog,
    is_manual_override_active,
    slew_steering,
)


def test_watchdog_applies_emergency_brake_at_timeout_boundary():
    state = apply_watchdog(
        command_age=0.2, timeout=0.2, throttle=0.8, brake=0.0,
        target_velocity=10.0, target_steering=0.5, velocity_error_sum=0.7,
    )
    assert state.triggered
    assert (state.throttle, state.brake) == (0.0, 1.0)
    assert state.target_velocity == 0.0
    assert state.target_steering == 0.0
    assert state.velocity_error_sum == 0.0


def test_watchdog_does_not_trigger_before_timeout():
    state = apply_watchdog(
        command_age=0.199, timeout=0.2, throttle=0.8, brake=0.0,
        target_velocity=10.0, target_steering=0.5, velocity_error_sum=0.7,
    )
    assert not state.triggered
    assert state.target_velocity == 10.0


def test_steering_slew_rate_is_limited_in_physical_radians():
    max_angle = 0.6108
    normalized = slew_steering(-1.0, 1.0, 2.0, max_angle, 0.05)
    assert (normalized + 1.0) * max_angle == pytest.approx(0.1)


def test_full_lock_reversal_takes_the_expected_physical_time():
    max_angle = 0.6108
    current = -1.0
    elapsed = 0.0
    while not math.isclose(current, 1.0):
        current = slew_steering(current, 1.0, 2.0, max_angle, 0.01)
        elapsed += 0.01
    assert elapsed == pytest.approx((2.0 * max_angle) / 2.0, abs=0.01)


@pytest.mark.parametrize(
    ('age', 'expected'), ((1.999, True), (2.0, False), (2.001, False)),
)
def test_manual_override_has_exact_two_second_window(age, expected):
    assert is_manual_override_active(age, timeout=2.0) is expected
