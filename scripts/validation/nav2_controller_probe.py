#!/usr/bin/env python3
"""Run real Nav2 RPP paths against a deterministic Ackermann pose fixture."""

import argparse
import math
import sys
import time

from action_msgs.msg import GoalStatus
from lifecycle_msgs.srv import GetState
from geometry_msgs.msg import PoseStamped, TransformStamped, Twist, TwistStamped
from nav2_msgs.action import FollowPath
from nav_msgs.msg import OccupancyGrid, Odometry, Path
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


WHEELBASE = 1.511
MAX_STEERING = 0.6108


def normalize_angle(value):
    return math.atan2(math.sin(value), math.cos(value))


def quaternion_from_yaw(yaw):
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def pose_stamped(x, y, yaw):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.orientation.z, pose.pose.orientation.w = quaternion_from_yaw(yaw)
    return pose


def u_turn_path():
    path = Path()
    path.header.frame_id = 'map'
    radius = 2.0
    for index in range(81):
        theta = math.pi * index / 80.0
        path.poses.append(pose_stamped(
            radius * math.sin(theta),
            radius * (1.0 - math.cos(theta)),
            theta,
        ))
    return path


def s_turn_path():
    path = Path()
    path.header.frame_id = 'map'
    step = 0.1
    for index in range(121):
        x = index * step
        if 3.0 < x < 9.0:
            y = 2.0 * math.sin(math.pi * (x - 3.0) / 3.0)
            dy_dx = (2.0 * math.pi / 3.0) * math.cos(
                math.pi * (x - 3.0) / 3.0)
        else:
            y = 0.0
            dy_dx = 0.0
        path.poses.append(pose_stamped(x, y, math.atan2(dy_dx, 1.0)))
    return path


class ControllerProbe(Node):
    def __init__(self):
        super().__init__('nav2_controller_probe')
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.map_pub = self.create_publisher(OccupancyGrid, '/map', map_qos)
        self.odom_pub = self.create_publisher(
            Odometry, '/odometry/filtered', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.tf_pub = TransformBroadcaster(self)
        self.static_tf_pub = StaticTransformBroadcaster(self)
        self.action = ActionClient(self, FollowPath, '/follow_path')
        self.controller_state = self.create_client(
            GetState, '/controller_server/get_state')
        self.commands = []
        self.steering = []
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.last_update = time.monotonic()
        self.target_velocity = 0.0
        self.target_omega = 0.0
        self.publish_map_once = True
        self.publish_static_tf()
        self.create_subscription(
            Twist, '/nav_cmd_vel', self.command_callback, 10)
        self.create_subscription(
            TwistStamped, '/car/control_request', self.steering_callback, 10)
        self.timer = self.create_timer(0.02, self.publish_fixture)

    def publish_static_tf(self):
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'odom'
        transform.transform.rotation.w = 1.0
        self.static_tf_pub.sendTransform(transform)

    def command_callback(self, message):
        self.target_velocity = message.linear.x
        self.target_omega = message.angular.z
        self.commands.append(
            (time.monotonic(), self.target_velocity, self.target_omega, self.x))

    def steering_callback(self, message):
        self.steering.append((time.monotonic(), message.twist.angular.z))

    def publish_map(self):
        grid = OccupancyGrid()
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.header.frame_id = 'map'
        grid.info.resolution = 0.05
        grid.info.width = 500
        grid.info.height = 500
        grid.info.origin.position.x = -10.0
        grid.info.origin.position.y = -10.0
        grid.info.origin.orientation.w = 1.0
        grid.data = [0] * (grid.info.width * grid.info.height)
        self.map_pub.publish(grid)

    def publish_fixture(self):
        now = time.monotonic()
        dt = min(now - self.last_update, 0.05)
        self.last_update = now
        self.x += self.target_velocity * math.cos(self.yaw) * dt
        self.y += self.target_velocity * math.sin(self.yaw) * dt
        self.yaw = normalize_angle(self.yaw + self.target_omega * dt)
        stamp = self.get_clock().now().to_msg()

        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = 'odom'
        transform.child_frame_id = 'base_link'
        transform.transform.translation.x = self.x
        transform.transform.translation.y = self.y
        transform.transform.rotation.z, transform.transform.rotation.w = (
            quaternion_from_yaw(self.yaw))
        self.tf_pub.sendTransform(transform)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.position.x = self.x
        odom.pose.pose.position.y = self.y
        odom.pose.pose.orientation.z, odom.pose.pose.orientation.w = (
            quaternion_from_yaw(self.yaw))
        odom.twist.twist.linear.x = self.target_velocity
        odom.twist.twist.angular.z = self.target_omega
        self.odom_pub.publish(odom)

        scan = LaserScan()
        scan.header.stamp = stamp
        scan.header.frame_id = 'base_link'
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.1
        scan.range_max = 30.0
        scan.ranges = [float('inf')] * 361
        self.scan_pub.publish(scan)
        if self.publish_map_once:
            self.publish_map()
            self.publish_map_once = False

    def reset_pose(self):
        self.x = 0.0
        self.y = 0.0
        self.yaw = 0.0
        self.target_velocity = 0.0
        self.target_omega = 0.0
        self.commands.clear()
        self.steering.clear()
        self.last_update = time.monotonic()

    def run_path(self, path):
        deadline = time.monotonic() + 30.0
        active = False
        while time.monotonic() < deadline:
            self.publish_map()
            rclpy.spin_once(self, timeout_sec=0.05)
            if not self.controller_state.wait_for_service(timeout_sec=0.05):
                continue
            state_future = self.controller_state.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, state_future, timeout_sec=0.5)
            state = state_future.result()
            if state is not None and state.current_state.label == 'active':
                active = True
                break
        if not active:
            raise RuntimeError('controller_server did not reach active state')
        if not self.action.wait_for_server(timeout_sec=2.0):
            raise RuntimeError('follow_path action unavailable')
        goal = FollowPath.Goal()
        path.header.stamp = self.get_clock().now().to_msg()
        goal.path = path
        goal.controller_id = 'FollowPath'
        goal.goal_checker_id = 'general_goal_checker'
        future = self.action.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError('FollowPath goal rejected')
        result_future = handle.get_result_async()
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline and not result_future.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        if not result_future.done():
            handle.cancel_goal_async()
            raise RuntimeError('FollowPath goal timed out')
        wrapped = result_future.result()
        if wrapped is None or wrapped.status != GoalStatus.STATUS_SUCCEEDED:
            status = wrapped.status if wrapped is not None else 'none'
            raise RuntimeError(f'FollowPath failed with status {status}')

    def u_turn_result(self, path):
        goal = path.poses[-1].pose
        final_error = math.hypot(self.x - goal.position.x, self.y - goal.position.y)
        final_yaw = math.atan2(2.0 * goal.orientation.z * goal.orientation.w,
                               1.0 - 2.0 * goal.orientation.z ** 2)
        yaw_error = abs(normalize_angle(self.yaw - final_yaw))
        moving = [sample for sample in self.commands if abs(sample[1]) > 0.1]
        spin_samples = [
            sample for sample in self.commands
            if abs(sample[1]) < 0.05 and abs(sample[2]) > 0.15]
        max_steering = max((abs(value) for _, value in self.steering), default=0.0)
        print(
            'RESULT mode=physical_u_turn '
            f'final=({self.x:.3f},{self.y:.3f},{self.yaw:.3f}) '
            f'goal_error={final_error:.3f} yaw_error={yaw_error:.3f} '
            f'moving_samples={len(moving)} spin_samples={len(spin_samples)} '
            f'steering_samples={len(self.steering)} '
            f'peak_steering={max_steering:.4f}', flush=True)
        if final_error > 0.35 or yaw_error > 0.35:
            raise RuntimeError('U-turn did not reach pose goal')
        if len(moving) < 20:
            raise RuntimeError('U-turn had insufficient forward motion')
        if spin_samples:
            raise RuntimeError('U-turn emitted in-place rotation commands')
        if max_steering > MAX_STEERING + 0.001:
            raise RuntimeError('bridge exceeded physical steering limit')

    def s_turn_result(self, path):
        straight = [sample[1] for sample in self.commands if sample[3] < 2.5]
        turn = [sample[1] for sample in self.commands if 3.2 < sample[3] < 8.8]
        reduced = [sample for sample in self.commands
                   if sample[3] < 3.0 and abs(sample[1]) < 2.5]
        max_steering = max((abs(value) for _, value in self.steering), default=0.0)
        straight_speed = max(straight, default=0.0)
        turn_speed = min((value for value in turn if value > 0.05), default=0.0)
        final_error = math.hypot(self.x - path.poses[-1].pose.position.x,
                                 self.y - path.poses[-1].pose.position.y)
        print(
            'RESULT mode=s_turn_braking '
            f'final=({self.x:.3f},{self.y:.3f}) goal_error={final_error:.3f} '
            f'straight_peak_speed={straight_speed:.3f} '
            f'turn_min_speed={turn_speed:.3f} '
            f'pre_turn_reduced_samples={len(reduced)} '
            f'steering_samples={len(self.steering)} '
            f'peak_steering={max_steering:.4f}', flush=True)
        if final_error > 0.4:
            raise RuntimeError('S-turn did not reach path goal')
        if straight_speed < 1.0 or turn_speed >= straight_speed - 0.2:
            raise RuntimeError('RPP did not regulate speed before S-turn curvature')
        if not reduced:
            raise RuntimeError('RPP reduced speed only after entering S-turn')
        if max_steering > MAX_STEERING + 0.001:
            raise RuntimeError('bridge exceeded physical steering limit')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('u_turn', 's_turn'))
    args = parser.parse_args()
    rclpy.init()
    node = ControllerProbe()
    try:
        node.reset_pose()
        path = u_turn_path() if args.mode == 'u_turn' else s_turn_path()
        node.run_path(path)
        if args.mode == 'u_turn':
            node.u_turn_result(path)
        else:
            node.s_turn_result(path)
    except RuntimeError as error:
        print(f'FAIL: {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print(f'PASS: Nav2 controller {args.mode} acceptance')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
