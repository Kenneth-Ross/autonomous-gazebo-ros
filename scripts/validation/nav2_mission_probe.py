#!/usr/bin/env python3
"""Provide deterministic Nav2 fixtures and evaluate Smac Hybrid U-turn planning."""

import math
import sys
import time

from builtin_interfaces.msg import Time
from geometry_msgs.msg import PoseStamped, TransformStamped
from nav2_msgs.action import ComputePathToPose
from lifecycle_msgs.srv import GetState
from nav_msgs.msg import OccupancyGrid, Odometry
import rclpy
from rclpy.action import ActionClient
from rclpy.duration import Duration
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


class Nav2MissionProbe(Node):
    def __init__(self):
        super().__init__('nav2_mission_probe')
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
        self.action = ActionClient(self, ComputePathToPose, '/compute_path_to_pose')
        self.planner_state = self.create_client(
            GetState, '/planner_server/get_state')
        self.publish_static_tf()
        self.timer = self.create_timer(0.05, self.publish_fixtures)

    def publish_static_tf(self):
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = 'map'
        transform.child_frame_id = 'odom'
        transform.transform.rotation.w = 1.0
        self.static_tf_pub.sendTransform(transform)

    def publish_fixtures(self):
        stamp = self.get_clock().now().to_msg()
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = 'odom'
        transform.child_frame_id = 'base_link'
        transform.transform.rotation.w = 1.0
        self.tf_pub.sendTransform(transform)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = 'odom'
        odom.child_frame_id = 'base_link'
        odom.pose.pose.orientation.w = 1.0
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

    def publish_map(self):
        grid = OccupancyGrid()
        grid.header.stamp = self.get_clock().now().to_msg()
        grid.header.frame_id = 'map'
        grid.info.resolution = 0.05
        grid.info.width = 400
        grid.info.height = 400
        grid.info.origin.position.x = -10.0
        grid.info.origin.position.y = -10.0
        grid.info.origin.orientation.w = 1.0
        grid.data = [0] * (grid.info.width * grid.info.height)
        self.map_pub.publish(grid)


def radius(first, middle, last):
    a = math.hypot(middle[0] - first[0], middle[1] - first[1])
    b = math.hypot(last[0] - middle[0], last[1] - middle[1])
    c = math.hypot(last[0] - first[0], last[1] - first[1])
    twice_area = abs(
        (middle[0] - first[0]) * (last[1] - first[1])
        - (middle[1] - first[1]) * (last[0] - first[0]))
    if twice_area < 1e-6:
        return float('inf')
    return (a * b * c) / (2.0 * twice_area)


def run_probe(node):
    deadline = time.monotonic() + 30.0
    active = False
    while time.monotonic() < deadline:
        node.publish_map()
        rclpy.spin_once(node, timeout_sec=0.05)
        if not node.planner_state.wait_for_service(timeout_sec=0.05):
            continue
        state_future = node.planner_state.call_async(GetState.Request())
        rclpy.spin_until_future_complete(node, state_future, timeout_sec=0.5)
        if (state_future.result() is not None
                and state_future.result().current_state.label == 'active'):
            active = True
            break
    if not active:
        raise RuntimeError('planner_server did not reach active state')
    if not node.action.wait_for_server(2.0):
        raise RuntimeError('compute_path_to_pose action unavailable')

    node.publish_map()
    goal = ComputePathToPose.Goal()
    goal.start = PoseStamped()
    goal.start.header.frame_id = 'map'
    goal.start.pose.orientation.w = 1.0
    goal.goal = PoseStamped()
    goal.goal.header.frame_id = 'map'
    goal.goal.pose.position.x = -3.0
    goal.goal.pose.orientation.z = 1.0
    goal.goal.pose.orientation.w = 0.0
    goal.planner_id = 'GridBased'
    future = node.action.send_goal_async(goal)
    rclpy.spin_until_future_complete(node, future, timeout_sec=10.0)
    handle = future.result()
    if handle is None or not handle.accepted:
        raise RuntimeError('U-turn planning goal rejected')
    result_future = handle.get_result_async()
    rclpy.spin_until_future_complete(node, result_future, timeout_sec=10.0)
    wrapped = result_future.result()
    if wrapped is None:
        raise RuntimeError('U-turn planning timed out')
    poses = wrapped.result.path.poses
    if len(poses) < 3:
        raise RuntimeError('U-turn path has fewer than three poses')

    points = [(pose.pose.position.x, pose.pose.position.y) for pose in poses]
    segments = [
        math.hypot(current[0] - previous[0], current[1] - previous[1])
        for previous, current in zip(points, points[1:])]
    radius_window = 5
    radii = [
        radius(
            points[index - radius_window], points[index],
            points[index + radius_window])
        for index in range(radius_window, len(points) - radius_window)]
    finite_radii = [value for value in radii if math.isfinite(value)]
    path_length = sum(segments)
    minimum_radius = min(finite_radii, default=float('inf'))
    minimum_segment = min(segments)
    lateral_extent = max(abs(point[1]) for point in points)
    print(
        'RESULT mode=u_turn '
        f'poses={len(poses)} path_length={path_length:.3f} '
        f'minimum_segment={minimum_segment:.4f} '
        f'radius_window={radius_window} minimum_radius={minimum_radius:.3f} '
        f'lateral_extent={lateral_extent:.3f}',
        flush=True,
    )
    if minimum_segment < 0.001:
        raise RuntimeError('planner emitted in-place path poses')
    if minimum_radius < 1.35:
        raise RuntimeError('measured path radius below 1.35 m tolerance')
    if lateral_extent < 1.0:
        raise RuntimeError('goal behind vehicle did not produce U-turn geometry')


def main():
    rclpy.init()
    node = Nav2MissionProbe()
    try:
        run_probe(node)
    except RuntimeError as error:
        print(f'FAIL: {error}', file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print('PASS: Smac Hybrid U-turn planning acceptance')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
