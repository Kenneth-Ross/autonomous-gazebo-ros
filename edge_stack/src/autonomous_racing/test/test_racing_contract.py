from autonomous_racing.racing_contract import RacingCommandGate
import pytest


def test_gate_requires_prepare_then_explicit_start():
    gate = RacingCommandGate()
    assert gate.output(0.0).reason == 'not_prepared'
    assert gate.start() is False
    gate.prepare()
    assert gate.output(0.0).reason == 'not_started'
    assert gate.start() is True
    assert gate.accept_candidate(2.0, 0.2, 1.0) is True
    assert gate.output(1.1).speed == pytest.approx(2.0)


def test_stale_candidate_latches_stop_until_new_prepare():
    gate = RacingCommandGate(freshness_timeout=0.2)
    gate.prepare()
    assert gate.start() is True
    assert gate.accept_candidate(1.0, 0.1, 10.0) is True
    assert gate.output(10.21).reason == 'candidate_stale'
    assert gate.latched_stop is True
    assert gate.start() is False
    gate.prepare()
    assert gate.latched_stop is False


def test_invalid_candidate_never_replaces_valid_command():
    gate = RacingCommandGate()
    gate.prepare()
    gate.start()
    assert gate.accept_candidate(1.0, 0.1, 4.0) is True
    assert gate.accept_candidate(6.0, 0.1, 4.1) is False
    assert gate.output(4.15).speed == pytest.approx(1.0)
    assert gate.accept_candidate(1.0, 0.7, 4.2) is False
    assert gate.output(4.16).speed == pytest.approx(1.0)


def test_recorder_heartbeat_is_hard_interlock_when_required():
    gate = RacingCommandGate(require_recorder_heartbeat=True)
    gate.prepare()
    assert gate.start(10.0) is True
    assert gate.accept_candidate(1.0, 0.1, 10.0) is True
    assert gate.output(10.19).speed == pytest.approx(1.0)
    assert gate.output(10.51).reason == 'recorder_missing'
    assert gate.latched_stop is True


def test_recorder_heartbeat_refresh_and_stale_latch():
    gate = RacingCommandGate(require_recorder_heartbeat=True)
    gate.prepare()
    gate.update_recorder_heartbeat(20.0)
    gate.start(20.0)
    gate.accept_candidate(1.0, 0.1, 20.0)
    assert gate.output(20.19).speed == pytest.approx(1.0)
    assert gate.output(20.51).reason == 'recorder_stale'
