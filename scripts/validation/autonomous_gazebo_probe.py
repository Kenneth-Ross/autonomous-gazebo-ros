#!/usr/bin/env python3
"""Exercise the ECU through ROS and evaluate the real Gazebo vehicle response."""

import argparse
import math
import sys
import time

from geometry_msgs.msg import TwistStamped
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import JointState
from std_msgs.msg import Float32


class AutonomousGazeboProbe(Node):
    def __init__(self):
        super().__init__('autonomous_gazebo_probe')
        self.odometry = []
        self.steering = []
        self.control_pub = self.create_publisher(
            TwistStamped, '/car/control_request', 10)
        self.brake_pub = self.create_publisher(Float32, '/car/brake', 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(JointState, '/joint_states', self.joint_cb, 10)

    def odom_cb(self, msg):
        position = msg.pose.pose.position
        velocity = msg.twist.twist.linear
        self.odometry.append((
            time.monotonic(), position.x, position.y,
            math.hypot(velocity.x, velocity.y),
        ))

    def joint_cb(self, msg):
        values = dict(zip(msg.name, msg.position))
        names = (
            'front_left_wheel_steering_joint',
            'front_right_wheel_steering_joint',
        )
        if all(name in values for name in names):
            self.steering.append(
                (time.monotonic(), values[names[0]], values[names[1]]))

    def publish_control(self, velocity, steering):
        msg = TwistStamped()
        msg.twist.linear.x = velocity
        msg.twist.angular.z = steering
        self.control_pub.publish(msg)

    def publish_brake(self):
        msg = Float32()
        msg.data = 1.0
        self.brake_pub.publish(msg)


def spin_for(node, duration, command=None, brake=False):
    deadline = time.monotonic() + duration
    while time.monotonic() < deadline:
        if command is not None:
            node.publish_control(*command)
        if brake:
            node.publish_brake()
        rclpy.spin_once(node, timeout_sec=0.02)


def wait_for_simulation(node):
    deadline = time.monotonic() + 15.0
    while time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.05)
        if node.odometry and node.steering:
            return
    raise RuntimeError('timed out waiting for /odom and /joint_states')


def distance(first, last):
    return math.hypot(last[1] - first[1], last[2] - first[2])


def evaluate_nominal(node):
    start = node.odometry[-1]
    steering_index = len(node.steering)
    spin_for(node, 4.0, command=(2.0, 0.5))
    end = node.odometry[-1]
    samples = node.steering[steering_index:]
    displacement = distance(start, end)
    lateral = abs(end[2] - start[2])
    angles = [value for _, left, right in samples for value in (left, right)]
    peak_steering = max(map(abs, angles), default=0.0)

    print(
        'RESULT mode=nominal '
        f'start=({start[1]:.3f},{start[2]:.3f}) '
        f'end=({end[1]:.3f},{end[2]:.3f}) '
        f'displacement={displacement:.3f} lateral={lateral:.3f} '
        f'steering_samples={len(samples)} peak_steering={peak_steering:.4f}',
        flush=True,
    )
    failures = []
    if displacement < 2.0:
        failures.append('vehicle displacement below 2.0 m')
    if lateral < 0.5:
        failures.append('curved request produced less than 0.5 m lateral motion')
    if len(samples) < 10:
        failures.append('fewer than 10 steering joint samples')
    if peak_steering < 0.01:
        failures.append('steering joints did not move')
    if peak_steering > 0.6115:
        failures.append('physical steering exceeded 0.6108 rad limit')
    if failures:
        raise RuntimeError('; '.join(failures))


def evaluate_adversarial(node):
    steering_index = len(node.steering)
    spin_for(node, 2.0, command=(2.0, -0.5))
    reversal_start = time.monotonic()
    spin_for(node, 2.0, command=(2.0, 0.5))
    moving_speed = node.odometry[-1][3]
    samples = node.steering[steering_index:]
    angles = [value for _, left, right in samples for value in (left, right)]
    negative = [stamp for stamp, left, right in samples if min(left, right) < -0.2]
    positive = [stamp for stamp, left, right in samples if max(left, right) > 0.2]
    positive_after_reversal = [
        stamp for stamp in positive if stamp >= reversal_start]
    reversal_time = (
        min(positive_after_reversal) - reversal_start
        if positive_after_reversal else float('inf'))
    adjacent_jump = max(
        (max(abs(current[1] - previous[1]), abs(current[2] - previous[2]))
         for previous, current in zip(samples, samples[1:])),
        default=0.0,
    )

    coast_start = node.odometry[-1]
    spin_for(node, 1.0)
    coast_end = node.odometry[-1]
    stopped_speed = coast_end[3]
    coast_distance = distance(coast_start, coast_end)

    spin_for(node, 0.1, brake=True)
    manual_start = node.odometry[-1]
    spin_for(node, 1.7, command=(2.0, 0.0))
    manual_end = node.odometry[-1]
    suppressed_distance = distance(manual_start, manual_end)
    spin_for(node, 1.0, command=(2.0, 0.0))
    recovery_end = node.odometry[-1]
    recovery_distance = distance(manual_end, recovery_end)

    print(
        'RESULT mode=adversarial '
        f'steering_samples={len(samples)} negative_lock={bool(negative)} '
        f'positive_lock={bool(positive)} max_joint_jump={adjacent_jump:.4f} '
        f'reversal_time={reversal_time:.3f} '
        f'moving_speed={moving_speed:.3f} stopped_speed={stopped_speed:.3f} '
        f'coast_distance={coast_distance:.3f} '
        f'manual_suppressed_distance={suppressed_distance:.3f} '
        f'recovery_distance={recovery_distance:.3f}',
        flush=True,
    )
    failures = []
    if not negative or not positive:
        failures.append('physical steering did not cross both turn directions')
    if max(map(abs, angles), default=0.0) > 0.6115:
        failures.append('physical steering exceeded 0.6108 rad limit')
    if adjacent_jump > 0.15:
        failures.append('steering joint snapped by more than 0.15 rad per sample')
    if not 0.5 <= reversal_time <= 0.8:
        failures.append('physical steering reversal time outside 0.5-0.8 seconds')
    if moving_speed < 0.5:
        failures.append('vehicle never reached moving speed')
    if stopped_speed > 0.2:
        failures.append('watchdog did not stop vehicle within one second')
    if coast_distance > 1.5:
        failures.append('watchdog stopping distance exceeded 1.5 m')
    if suppressed_distance > 0.3:
        failures.append('manual override did not suppress autonomous motion')
    if recovery_distance < 0.3:
        failures.append('autonomous motion did not recover after manual timeout')
    if failures:
        raise RuntimeError('; '.join(failures))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('nominal', 'adversarial'))
    args = parser.parse_args()
    rclpy.init()
    node = AutonomousGazeboProbe()
    try:
        wait_for_simulation(node)
        if args.mode == 'nominal':
            evaluate_nominal(node)
        else:
            evaluate_adversarial(node)
    except RuntimeError as error:
        print(f'FAIL: {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print(f'PASS: Gazebo {args.mode} autonomous acceptance')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
