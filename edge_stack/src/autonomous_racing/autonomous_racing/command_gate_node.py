#!/usr/bin/env python3
"""ROS command gate: only this node publishes autonomous car commands."""

from autonomous_racing.racing_contract import RacingCommandGate
from autonomous_racing_msgs.msg import (
    ControlCandidate, RecorderHeartbeat, SupervisorStatus)
from autonomous_racing_msgs.srv import AbortRun, PrepareRun, StartRun
from geometry_msgs.msg import TwistStamped
import rclpy
from rclpy.node import Node


class CommandGateNode(Node):
    """Publish zero until explicitly prepared and started; latch safety faults."""

    def __init__(self):
        super().__init__('racing_command_gate')
        self.declare_parameter('freshness_timeout', 0.2)
        self.declare_parameter('recorder_timeout', 0.5)
        self.declare_parameter('max_speed', 5.0)
        self.declare_parameter('max_steering', 0.6108)
        self.declare_parameter('require_recorder_heartbeat', False)
        self.declare_parameter('run_id', '')
        self.run_id = str(self.get_parameter('run_id').value)
        self.gate = RacingCommandGate(
            freshness_timeout=self.get_parameter('freshness_timeout').value,
            recorder_timeout=self.get_parameter('recorder_timeout').value,
            max_speed=self.get_parameter('max_speed').value,
            max_steering=self.get_parameter('max_steering').value,
            require_recorder_heartbeat=self.get_parameter(
                'require_recorder_heartbeat').value)
        self.command_pub = self.create_publisher(
            TwistStamped, '/car/control_request', 10)
        self.status_pub = self.create_publisher(
            SupervisorStatus, '/racing/supervisor_status', 10)
        self.create_subscription(
            ControlCandidate, '/racing/control_candidate',
            self.candidate_callback, 10)
        self.create_subscription(
            RecorderHeartbeat, '/racing/recorder/heartbeat',
            self.recorder_callback, 10)
        self.create_service(PrepareRun, '/racing/prepare', self.prepare_callback)
        self.create_service(StartRun, '/racing/start', self.start_callback)
        self.create_service(AbortRun, '/racing/abort', self.abort_callback)
        self.create_timer(0.02, self.publish_command)

    def now_seconds(self):
        return self.get_clock().now().nanoseconds / 1e9

    def candidate_callback(self, message):
        # Controller emits invalid startup candidates until path/odometry exist.
        # They must not latch a run before explicit operator start.
        if not self.gate.prepared or not self.gate.armed:
            return
        if not message.valid:
            self.gate.abort(message.fault_reason or 'candidate_invalid')
            return
        accepted = self.gate.accept_candidate(
            message.speed, message.steering, self.now_seconds())
        if not accepted:
            self.gate.abort('candidate_invalid')

    def recorder_callback(self, message):
        now = self.now_seconds()
        healthy = message.bag_healthy and message.state in (
            RecorderHeartbeat.READY, RecorderHeartbeat.RECORDING)
        if healthy:
            self.gate.update_recorder_heartbeat(now)
        elif self.gate.armed and self.gate.require_recorder_heartbeat:
            self.gate.abort('recorder_unhealthy')

    def prepare_callback(self, request, response):
        self.gate.prepare()
        if request.run_id_hint:
            self.run_id = request.run_id_hint
        response.success = True
        response.run_id = self.run_id
        response.message = 'run prepared; explicit start required'
        return response

    def start_callback(self, request, response):
        response.success = (
            bool(request.start) and self.gate.start(self.now_seconds()))
        if not request.start:
            self.gate.abort('operator_stop')
            response.success = True
        response.message = self.gate.stop_reason or 'run started'
        return response

    def abort_callback(self, request, response):
        self.gate.abort(request.reason or 'operator_abort')
        response.success = True
        response.message = self.gate.stop_reason
        return response

    def _status_state(self, output):
        if self.gate.latched_stop:
            return (SupervisorStatus.ABORTED if
                    self.gate.stop_reason in ('operator_abort', 'operator_stop') else
                    SupervisorStatus.FAILED)
        if not self.gate.prepared:
            return SupervisorStatus.IDLE
        if not self.gate.armed:
            return SupervisorStatus.READY
        return SupervisorStatus.RACING

    def publish_command(self):
        now = self.now_seconds()
        output = self.gate.output(now)
        stamp = self.get_clock().now().to_msg()
        message = TwistStamped()
        message.header.stamp = stamp
        message.header.frame_id = 'base_link'
        message.twist.linear.x = output.speed
        message.twist.angular.z = output.steering
        self.command_pub.publish(message)

        status = SupervisorStatus()
        status.header.stamp = stamp
        status.run_id = self.run_id
        status.state = self._status_state(output)
        status.stop_reason = output.reason
        status.controller_ready = output.reason == ''
        status.recorder_ready = self.gate.recorder_ready(now)
        status.planner_ready = status.controller_ready
        self.status_pub.publish(status)


def main(args=None):
    rclpy.init(args=args)
    node = CommandGateNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
