import pytest

from my_gazebo_package_py.driving_model_control import (
    apply_watchdog,
    is_manual_override_active,
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


@pytest.mark.parametrize(
    ('age', 'expected'), ((1.999, True), (2.0, False), (2.001, False)),
)
def test_manual_override_has_exact_two_second_window(age, expected):
    assert is_manual_override_active(age, timeout=2.0) is expected
