#!/usr/bin/env python3
"""Exercise Nav2 through the real Gazebo Ackermann vehicle."""

import argparse
import math
import sys
import time

from action_msgs.msg import GoalStatus
from geometry_msgs.msg import PoseStamped, TransformStamped, Twist, TwistStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import FollowPath, NavigateToPose
from nav_msgs.msg import OccupancyGrid, Odometry, Path
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import JointState, LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


MAX_STEERING = 0.6108


def normalize_angle(value):
    return math.atan2(math.sin(value), math.cos(value))


def quaternion_from_yaw(yaw):
    return math.sin(yaw / 2.0), math.cos(yaw / 2.0)


def yaw_from_quaternion(quaternion):
    return math.atan2(
        2.0 * quaternion.z * quaternion.w,
        1.0 - 2.0 * quaternion.z * quaternion.z,
    )


def pose_stamped(x, y, yaw):
    pose = PoseStamped()
    pose.header.frame_id = 'map'
    pose.pose.position.x = x
    pose.pose.position.y = y
    pose.pose.orientation.z, pose.pose.orientation.w = quaternion_from_yaw(yaw)
    return pose


def u_turn_path(start_x, start_y, start_yaw):
    path = Path()
    path.header.frame_id = 'map'
    # Physical steering limit requires radius >= L/tan(0.6108) = 2.18 m.
    radius = 3.0
    for index in range(101):
        theta = math.pi * index / 100.0
        local_x = radius * math.sin(theta)
        local_y = radius * (1.0 - math.cos(theta))
        path.poses.append(pose_stamped(
            start_x + local_x * math.cos(start_yaw) - local_y * math.sin(start_yaw),
            start_y + local_x * math.sin(start_yaw) + local_y * math.cos(start_yaw),
            start_yaw + theta,
        ))
    return path


def s_turn_path(start_x, start_y):
    path = Path()
    path.header.frame_id = "map"
    # Smooth two-sided curvature stays inside the physical radius while
    # entering RPP 2.5 m speed-regulation band. The sin^2 envelope makes
    # tangent and heading continuous at both ends of the S.
    step = 0.1
    straight = 4.0
    turn_length = 10.0
    amplitude = 0.8
    total = straight + turn_length + 1.0
    for index in range(round(total / step) + 1):
        distance = index * step
        x = start_x + distance
        if straight < distance < straight + turn_length:
            phase = (distance - straight) / turn_length
            envelope = math.sin(math.pi * phase) ** 2
            y = start_y + amplitude * math.sin(2.0 * math.pi * phase) * envelope
            # Derivative of sin(2*pi*u) * sin(pi*u)^2 with respect to x.
            derivative = (
                2.0 * math.pi * math.cos(2.0 * math.pi * phase) * envelope
                + math.pi * math.sin(2.0 * math.pi * phase)
                * math.sin(2.0 * math.pi * phase)
            ) * amplitude / turn_length
        else:
            y = start_y
            derivative = 0.0
        path.poses.append(pose_stamped(x, y, math.atan2(derivative, 1.0)))
    return path


class GazeboNav2Probe(Node):
    def __init__(self):
        super().__init__('gazebo_nav2_mission_probe')
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.map_pub = self.create_publisher(OccupancyGrid, '/map', map_qos)
        self.filtered_odom_pub = self.create_publisher(
            Odometry, '/odometry/filtered', 10)
        self.scan_pub = self.create_publisher(LaserScan, '/scan', 10)
        self.tf_pub = TransformBroadcaster(self)
        self.static_tf_pub = StaticTransformBroadcaster(self)
        self.navigate_action = ActionClient(
            self, NavigateToPose, '/navigate_to_pose')
        self.follow_action = ActionClient(self, FollowPath, '/follow_path')
        self.bt_state = self.create_client(GetState, '/bt_navigator/get_state')
        self.controller_state = self.create_client(
            GetState, '/controller_server/get_state')
        self.odom = None
        self.odom_history = []
        self.plan = None
        self.commands = []
        self.steering = []
        self.joint_history = []
        self.create_subscription(Odometry, '/odom', self.odom_callback, 10)
        self.create_subscription(Path, '/plan', self.plan_callback, 10)
        self.create_subscription(Twist, '/nav_cmd_vel', self.command_callback, 10)
        self.create_subscription(
            TwistStamped, '/car/control_request', self.control_callback, 10)
        self.create_subscription(JointState, '/joint_states', self.joint_callback, 10)
        self.timer = self.create_timer(0.1, self.publish_fixtures)
        self.publish_static_tf()

    def publish_static_tf(self):
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'odom'
        transform.transform.rotation.w = 1.0
        self.static_tf_pub.sendTransform(transform)

    def odom_callback(self, message):
        self.odom = message
        position = message.pose.pose.position
        yaw = yaw_from_quaternion(message.pose.pose.orientation)
        self.odom_history.append((
            time.monotonic(), position.x, position.y, yaw,
            math.hypot(message.twist.twist.linear.x,
                       message.twist.twist.linear.y),
        ))
        self.filtered_odom_pub.publish(message)
        transform = TransformStamped()
        transform.header = message.header
        transform.header.frame_id = message.header.frame_id or 'odom'
        transform.child_frame_id = message.child_frame_id or 'base_link'
        transform.transform.translation.x = position.x
        transform.transform.translation.y = position.y
        transform.transform.rotation = message.pose.pose.orientation
        self.tf_pub.sendTransform(transform)

    def plan_callback(self, message):
        self.plan = message

    def command_callback(self, message):
        pose = self.odom.pose.pose if self.odom is not None else None
        self.commands.append((
            time.monotonic(), message.linear.x, message.angular.z,
            pose.position.x if pose else 0.0,
            pose.position.y if pose else 0.0,
        ))

    def control_callback(self, message):
        self.steering.append((time.monotonic(), message.twist.angular.z))

    def joint_callback(self, message):
        values = dict(zip(message.name, message.position))
        names = (
            'front_left_wheel_steering_joint',
            'front_right_wheel_steering_joint',
        )
        if all(name in values for name in names):
            self.joint_history.append((
                time.monotonic(), values[names[0]], values[names[1]]))

    def publish_fixtures(self):
        stamp = self.get_clock().now().to_msg()
        grid = OccupancyGrid()
        grid.header.stamp = stamp
        grid.header.frame_id = 'map'
        grid.info.resolution = 0.05
        grid.info.width = 600
        grid.info.height = 500
        grid.info.origin.position.x = -10.0
        grid.info.origin.position.y = -10.0
        grid.info.origin.orientation.w = 1.0
        grid.data = [0] * (grid.info.width * grid.info.height)
        self.map_pub.publish(grid)

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

    def wait_for_odom(self):
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            rclpy.spin_once(self, timeout_sec=0.05)
            if self.odom is not None:
                return
        raise RuntimeError('timed out waiting for Gazebo /odom')

    def wait_for_state(self, client, label):
        deadline = time.monotonic() + 45.0
        while time.monotonic() < deadline:
            self.publish_fixtures()
            rclpy.spin_once(self, timeout_sec=0.05)
            if not client.wait_for_service(timeout_sec=0.05):
                continue
            future = client.call_async(GetState.Request())
            rclpy.spin_until_future_complete(self, future, timeout_sec=0.5)
            state = future.result()
            if state is not None and state.current_state.label == 'active':
                return
        raise RuntimeError(f'{label} did not reach active state')

    def navigate_u_turn(self):
        self.wait_for_state(self.controller_state, 'controller_server')
        if not self.follow_action.wait_for_server(timeout_sec=5.0):
            raise RuntimeError('follow_path action unavailable')
        start = self.odom_history[-1]
        path = u_turn_path(start[1], start[2], start[3])
        goal = FollowPath.Goal()
        path.header.stamp = self.get_clock().now().to_msg()
        goal.path = path
        goal.controller_id = 'FollowPath'
        goal.goal_checker_id = 'general_goal_checker'
        future = self.follow_action.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError('FollowPath U-turn goal rejected')
        result_future = handle.get_result_async()
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline and not result_future.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        if not result_future.done():
            handle.cancel_goal_async()
            raise RuntimeError('FollowPath U-turn timed out')
        wrapped = result_future.result()
        if wrapped is None or wrapped.status != GoalStatus.STATUS_SUCCEEDED:
            status = wrapped.status if wrapped is not None else 'none'
            raise RuntimeError(f'FollowPath U-turn failed with status {status}')
        self.evaluate_u_turn(start, path)

    def follow_s_turn(self):
        self.wait_for_state(self.controller_state, 'controller_server')
        if not self.follow_action.wait_for_server(timeout_sec=5.0):
            raise RuntimeError('follow_path action unavailable')
        start = self.odom_history[-1]
        path = s_turn_path(start[1], start[2])
        goal = FollowPath.Goal()
        path.header.stamp = self.get_clock().now().to_msg()
        goal.path = path
        goal.controller_id = 'FollowPath'
        goal.goal_checker_id = 'general_goal_checker'
        future = self.follow_action.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=10.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError('FollowPath goal rejected')
        result_future = handle.get_result_async()
        deadline = time.monotonic() + 90.0
        while time.monotonic() < deadline and not result_future.done():
            rclpy.spin_once(self, timeout_sec=0.05)
        if not result_future.done():
            handle.cancel_goal_async()
            raise RuntimeError('FollowPath timed out')
        wrapped = result_future.result()
        if wrapped is None or wrapped.status != GoalStatus.STATUS_SUCCEEDED:
            status = wrapped.status if wrapped is not None else 'none'
            raise RuntimeError(f'FollowPath failed with status {status}')
        self.evaluate_s_turn(path)

    def evaluate_u_turn(self, start, path):
        end = self.odom_history[-1]
        goal = path.poses[-1].pose
        goal_yaw = yaw_from_quaternion(goal.orientation)
        goal_error = math.hypot(end[1] - goal.position.x,
                                end[2] - goal.position.y)
        yaw_error = abs(normalize_angle(end[3] - goal_yaw))
        spin = [sample for sample in self.commands
                if abs(sample[1]) < 0.05 and abs(sample[2]) > 0.15]
        max_steering = max((abs(value) for _, value in self.steering), default=0.0)
        lateral = max((math.hypot(
            p.pose.position.x - start[1], p.pose.position.y - start[2])
                       for p in path.poses), default=0.0)
        print(
            'RESULT mode=gazebo_physical_u_turn '
            f'goal_error={goal_error:.3f} yaw_error={yaw_error:.3f} '
            f'path_poses={len(path.poses)} lateral_extent={lateral:.3f} '
            f'spin_samples={len(spin)} joint_samples={len(self.joint_history)} '
            f'peak_bridge_steering={max_steering:.4f}', flush=True)
        if goal_error > 0.5 or yaw_error > 0.5:
            raise RuntimeError('Gazebo vehicle did not reach U-turn goal')
        if lateral < 3.0:
            raise RuntimeError('U-turn path lacked physical lateral extent')
        if spin:
            raise RuntimeError('Gazebo mission emitted in-place rotation commands')
        if not self.joint_history:
            raise RuntimeError('no Gazebo steering joint samples captured')
        if max((abs(value) for _, left, right in self.joint_history
                for value in (left, right)), default=0.0) > MAX_STEERING + 0.001:
            raise RuntimeError('Gazebo steering exceeded physical limit')

    def evaluate_s_turn(self, path):
        end = self.odom_history[-1]
        start_x = path.poses[0].pose.position.x
        goal = path.poses[-1].pose
        goal_error = math.hypot(end[1] - goal.position.x,
                                end[2] - goal.position.y)
        # High-curvature S segment begins near x=7.3 m; the smooth envelope
        # starts earlier so RPP has a measurable pre-turn lookahead window.
        turn_start = start_x + 7.0
        turn_end = turn_start + 4.0
        straight = [sample[1] for sample in self.commands
                    if sample[3] < start_x + 1.5]
        turn = [sample[1] for sample in self.commands
                if turn_start + 1.0 < sample[3] < turn_end - 1.0]
        reduced = [sample for sample in self.commands
                   if start_x + 1.0 < sample[3] < turn_start + 0.1
                   and abs(sample[1]) < 0.9]
        max_steering = max((abs(value) for _, value in self.steering), default=0.0)
        straight_speed = max(straight, default=0.0)
        turn_speed = min((value for value in turn if value > 0.05), default=0.0)
        print(
            "RESULT mode=gazebo_physical_s_turn "
            f"goal_error={goal_error:.3f} straight_peak_speed={straight_speed:.3f} "
            f"turn_min_speed={turn_speed:.3f} pre_turn_reduced_samples={len(reduced)} "
            f"joint_samples={len(self.joint_history)} peak_bridge_steering={max_steering:.4f}",
            flush=True)
        if goal_error > 0.5:
            raise RuntimeError("Gazebo vehicle did not reach S-turn goal")
        if straight_speed < 0.6 or turn_speed >= straight_speed - 0.05:
            raise RuntimeError("RPP did not regulate Gazebo speed before S-turn")
        if not self.joint_history:
            raise RuntimeError("no Gazebo steering joint samples captured")
        if max((abs(value) for _, left, right in self.joint_history
                for value in (left, right)), default=0.0) > MAX_STEERING + 0.001:
            raise RuntimeError("Gazebo steering exceeded physical limit")



def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('u_turn', 's_turn'))
    args, ros_args = parser.parse_known_args()
    rclpy.init(args=ros_args)
    node = GazeboNav2Probe()
    try:
        node.wait_for_odom()
        if args.mode == 'u_turn':
            node.navigate_u_turn()
        else:
            node.follow_s_turn()
    except RuntimeError as error:
        print(f'FAIL: {error}', file=sys.stderr, flush=True)
        if node.odom_history:
            last = node.odom_history[-1]
            xs = [sample[1] for sample in node.odom_history]
            ys = [sample[2] for sample in node.odom_history]
            velocities = [sample[1] for sample in node.commands]
            omegas = [sample[2] for sample in node.commands]
            first = node.odom_history[0]
            print(
                'DIAGNOSTIC odom_samples=%d first=(%.3f,%.3f,%.3f) '
                'last=(%.3f,%.3f,%.3f) x_range=(%.3f,%.3f) '
                'y_range=(%.3f,%.3f) commands=%d velocity_range=(%.3f,%.3f) '
                'omega_range=(%.3f,%.3f)' % (
                    len(node.odom_history), first[1], first[2], first[3],
                    last[1], last[2], last[3], min(xs), max(xs), min(ys),
                    max(ys), len(node.commands), min(velocities, default=0.0),
                    max(velocities, default=0.0), min(omegas, default=0.0),
                    max(omegas, default=0.0)),
                file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print(f'PASS: Gazebo Nav2 {args.mode} acceptance')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
