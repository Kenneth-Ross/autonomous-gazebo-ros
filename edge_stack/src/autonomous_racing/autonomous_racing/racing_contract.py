"""Pure safety contracts for autonomous racing command ownership."""

from __future__ import annotations

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class GateOutput:
    """Command emitted by the gate and the reason for a zero command."""

    speed: float
    steering: float
    reason: str


@dataclass(frozen=True)
class _Candidate:
    speed: float
    steering: float
    received_at: float


class RacingCommandGate:
    """Independent prepare/start/abort gate with bounded input freshness."""

    def __init__(self, freshness_timeout=0.2, recorder_timeout=0.5,
                 max_speed=5.0, max_steering=0.6108,
                 require_recorder_heartbeat=False):
        values = (freshness_timeout, recorder_timeout, max_speed, max_steering)
        if not all(math.isfinite(float(value)) and value > 0 for value in values):
            raise ValueError('gate limits must be finite and positive')
        self.freshness_timeout = float(freshness_timeout)
        self.recorder_timeout = float(recorder_timeout)
        self.max_speed = float(max_speed)
        self.max_steering = float(max_steering)
        self.require_recorder_heartbeat = bool(require_recorder_heartbeat)
        self.prepared = False
        self.armed = False
        self.latched_stop = False
        self.stop_reason = 'not_prepared'
        self._candidate = None
        self._armed_at = None
        self._recorder_received_at = None

    def prepare(self):
        """Reset run-local state; motion remains disabled until ``start``."""
        self.prepared = True
        self.armed = False
        self.latched_stop = False
        self.stop_reason = 'not_started'
        self._candidate = None
        self._armed_at = None
        self._recorder_received_at = None

    def start(self, now=0.0):
        """Open gate only after prepare and before any latched stop."""
        if not self.prepared or self.latched_stop:
            return False
        self.armed = True
        self._armed_at = float(now)
        self.stop_reason = ''
        return True

    def abort(self, reason='operator_abort'):
        """Latch a stop; only a later ``prepare`` can clear it."""
        self.armed = False
        self._armed_at = None
        self.latched_stop = True
        self.stop_reason = str(reason) or 'operator_abort'

    def accept_candidate(self, speed, steering, received_at):
        """Accept bounded finite candidate; reject invalid command atomically."""
        values = (speed, steering, received_at)
        if not all(math.isfinite(float(value)) for value in values):
            return False
        if speed < 0.0 or speed > self.max_speed:
            return False
        if abs(steering) > self.max_steering:
            return False
        self._candidate = _Candidate(float(speed), float(steering),
                                     float(received_at))
        return True

    def update_recorder_heartbeat(self, received_at):
        """Refresh recorder liveness for runs that require server recording."""
        if not math.isfinite(float(received_at)):
            return False
        self._recorder_received_at = float(received_at)
        return True

    def recorder_ready(self, now):
        """Return whether recorder heartbeat is fresh or recorder is optional."""
        if not self.require_recorder_heartbeat:
            return True
        if self._recorder_received_at is None:
            return (self._armed_at is not None and
                    float(now) - self._armed_at <= self.recorder_timeout)
        return float(now) - self._recorder_received_at <= self.recorder_timeout

    def _check_recorder(self, now):
        if not self.require_recorder_heartbeat:
            return None
        if self._recorder_received_at is None:
            if self._armed_at is not None and (
                    float(now) - self._armed_at > self.recorder_timeout):
                return 'recorder_missing'
            return None
        if float(now) - self._recorder_received_at > self.recorder_timeout:
            return 'recorder_stale'
        return None

    def output(self, now):
        """Return safe command, latching stale/missing input failures."""
        if self.latched_stop:
            return GateOutput(0.0, 0.0, self.stop_reason)
        if not self.prepared:
            return GateOutput(0.0, 0.0, 'not_prepared')
        if not self.armed:
            return GateOutput(0.0, 0.0, 'not_started')
        recorder_reason = self._check_recorder(now)
        if recorder_reason:
            self.abort(recorder_reason)
            return GateOutput(0.0, 0.0, self.stop_reason)
        if self._candidate is None:
            if self._armed_at is not None and now - self._armed_at <= self.freshness_timeout:
                return GateOutput(0.0, 0.0, 'candidate_missing')
            self.abort('candidate_missing')
            return GateOutput(0.0, 0.0, self.stop_reason)
        age = float(now) - self._candidate.received_at
        if age < -0.05:
            self.abort('candidate_clock')
            return GateOutput(0.0, 0.0, self.stop_reason)
        if age > self.freshness_timeout:
            self.abort('candidate_stale')
            return GateOutput(0.0, 0.0, self.stop_reason)
        return GateOutput(self._candidate.speed, self._candidate.steering, '')
