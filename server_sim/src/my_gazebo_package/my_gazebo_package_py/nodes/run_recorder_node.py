#!/usr/bin/python3
"""MCAP run coordinator for autonomous-racing server artifacts."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os

from autonomous_racing_msgs.msg import RecorderHeartbeat
from autonomous_racing_msgs.srv import AbortRun, PrepareRun, StartRun
from my_gazebo_package_py.run_artifacts import (
    McapRecorderProcess, OPTIONAL_TOPICS, REQUIRED_TOPICS, RunArtifacts)
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_srvs.srv import Trigger


class RunRecorderNode(Node):
    """Prepare, start, stop, and abort one allowlisted MCAP run."""

    def __init__(self):
        super().__init__('racing_run_recorder')
        self.declare_parameter('artifact_root', 'telemetry')
        self.declare_parameter('run_id', '')
        self.declare_parameter('track_name', 'catalunya')
        self.declare_parameter('seed', -1)
        self.declare_parameter('topics', list(REQUIRED_TOPICS + OPTIONAL_TOPICS))
        self.artifacts = None
        self.recorder = None
        self._state = RecorderHeartbeat.STARTING
        self._detail = 'waiting for prepare'
        self.heartbeat_pub = self.create_publisher(
            RecorderHeartbeat, '/racing/recorder/heartbeat', 10)
        self.create_service(
            PrepareRun, '/racing/recorder/prepare', self.prepare_callback)
        self.create_service(
            StartRun, '/racing/recorder/start', self.start_callback)
        self.create_service(
            Trigger, '/racing/recorder/stop', self.stop_callback)
        self.create_service(
            AbortRun, '/racing/recorder/abort', self.abort_callback)
        self.create_timer(0.1, self.publish_heartbeat)

    def _stamp(self):
        return datetime.now(timezone.utc)

    def _run_id(self):
        configured = str(self.get_parameter('run_id').value)
        if configured:
            return configured
        return f"race_{self._stamp().strftime('%Y%m%dT%H%M%SZ')}"

    def prepare_callback(self, request, response):
        self.get_logger().info(
            f'prepare request received: run_id_hint={request.run_id_hint!r} '
            f'active={self.recorder is not None}')
        if self.recorder is not None:
            response.message = 'recorder already active'
            return response
        self._state = RecorderHeartbeat.STARTING
        try:
            topics = tuple(self.get_parameter('topics').value)
            run_id = request.run_id_hint or self._run_id()
            track_name = request.track_name or self.get_parameter('track_name').value
            seed = request.seed if request.seed != 0 else int(self.get_parameter('seed').value)
            self.artifacts = RunArtifacts.prepare(
                self.get_parameter('artifact_root').value, run_id,
                metadata={
                    'track': track_name,
                    'seed': int(seed),
                    'dirty_worktree': None,
                    'host_identity': os.uname().nodename,
                    'edge_identity': None,
                }, topics=topics, started_at=self._stamp())
            self.recorder = McapRecorderProcess(self.artifacts)
            command = self.recorder.start()
            self.get_logger().info(
                f'recorder process started: run_id={self.artifacts.run_id!r}')
        except Exception as error:
            self.get_logger().error(f'run recorder prepare failed: {error}')
            self.recorder = None
            self.artifacts = None
            self._state = RecorderHeartbeat.INCOMPLETE
            self._detail = str(error)
            response.message = str(error)
            return response
        self._state = RecorderHeartbeat.RECORDING
        self._detail = 'recording started'
        response.success = True
        response.run_id = self.artifacts.run_id
        response.message = 'recording started: ' + ' '.join(command)
        self.get_logger().info(f'prepare response ready: run_id={response.run_id!r}')
        return response

    def start_callback(self, request, response):
        if not request.start:
            response.success = False
            response.message = 'recorder start request must be true; use stop or abort'
            return response
        response.success = self.recorder is not None
        response.message = 'recorder active' if response.success else 'recorder is not active'
        return response

    def _finish(self, terminal_state, heartbeat_state):
        if self.recorder is None:
            raise RuntimeError('recorder is not active')
        result = self.recorder.stop(terminal_state=terminal_state)
        self.recorder = None
        self.artifacts = None
        self._state = heartbeat_state
        self._detail = terminal_state.lower()
        return result

    def stop_callback(self, _request, response):
        try:
            result = self._finish('COMPLETE', RecorderHeartbeat.COMPLETE)
        except Exception as error:
            response.message = str(error)
            return response
        response.success = True
        response.message = json.dumps(result, sort_keys=True)
        return response

    def abort_callback(self, request, response):
        try:
            result = self._finish('ABORTED', RecorderHeartbeat.ABORTED)
        except Exception as error:
            response.message = str(error)
            return response
        if request.reason:
            self._detail = request.reason
        response.success = True
        response.message = json.dumps(result, sort_keys=True)
        return response

    def publish_heartbeat(self):
        message = RecorderHeartbeat()
        message.header.stamp = self.get_clock().now().to_msg()
        message.run_id = self.artifacts.run_id if self.artifacts is not None else ''
        message.state = self._state
        message.bag_healthy = (self.recorder is not None and
                               self.recorder.process is not None and
                               self.recorder.process.poll() is None)
        message.detail = self._detail
        self.heartbeat_pub.publish(message)

    def destroy_node(self):
        if self.recorder is not None:
            try:
                self._finish('INCOMPLETE', RecorderHeartbeat.INCOMPLETE)
            except Exception as error:
                self.get_logger().error(f'failed to finalize recorder: {error}')
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = RunRecorderNode()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
