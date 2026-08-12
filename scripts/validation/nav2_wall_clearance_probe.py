#!/usr/bin/env python3
"""Verify Nav2 global-costmap wall inflation and free-space clearance."""

import math
import sys
import time

from geometry_msgs.msg import PoseStamped, TransformStamped
from lifecycle_msgs.srv import GetState
from nav2_msgs.action import ComputePathToPose
from nav2_msgs.msg import Costmap
from nav_msgs.msg import OccupancyGrid, Odometry
import rclpy
from rclpy.action import ActionClient
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs.msg import LaserScan
from tf2_ros import StaticTransformBroadcaster, TransformBroadcaster


class WallClearanceProbe(Node):
    def __init__(self):
        super().__init__("nav2_wall_clearance_probe")
        map_qos = QoSProfile(
            depth=1,
            durability=DurabilityPolicy.TRANSIENT_LOCAL,
            reliability=ReliabilityPolicy.RELIABLE,
        )
        self.map_pub = self.create_publisher(OccupancyGrid, "/map", map_qos)
        self.odom_pub = self.create_publisher(
            Odometry, "/odometry/filtered", 10)
        self.scan_pub = self.create_publisher(LaserScan, "/scan", 10)
        self.costmap = None
        self.costmap_sub = self.create_subscription(
            Costmap, "/global_costmap/costmap_raw", self.costmap_callback,
            map_qos)
        self.lifecycle_states = {
            name: self.create_client(GetState, f"/{name}/get_state")
            for name in (
                "planner_server",
                "controller_server",
                "behavior_server",
                "bt_navigator",
                "waypoint_follower",
            )
        }
        self.compute_path = ActionClient(
            self, ComputePathToPose, "/compute_path_to_pose")
        self.tf_pub = TransformBroadcaster(self)
        self.static_tf_pub = StaticTransformBroadcaster(self)
        self.timer = self.create_timer(0.1, self.publish_fixtures)
        self.publish_static_tf()

    def costmap_callback(self, message):
        self.costmap = message

    def publish_static_tf(self):
        transform = TransformStamped()
        transform.header.stamp = self.get_clock().now().to_msg()
        transform.header.frame_id = "map"
        transform.child_frame_id = "odom"
        transform.transform.rotation.w = 1.0
        self.static_tf_pub.sendTransform(transform)

    def publish_fixtures(self):
        stamp = self.get_clock().now().to_msg()
        transform = TransformStamped()
        transform.header.stamp = stamp
        transform.header.frame_id = "odom"
        transform.child_frame_id = "base_link"
        transform.transform.rotation.w = 1.0
        self.tf_pub.sendTransform(transform)

        odom = Odometry()
        odom.header.stamp = stamp
        odom.header.frame_id = "odom"
        odom.child_frame_id = "base_link"
        odom.pose.pose.orientation.w = 1.0
        self.odom_pub.publish(odom)

        scan = LaserScan()
        scan.header.stamp = stamp
        scan.header.frame_id = "base_link"
        scan.angle_min = -math.pi
        scan.angle_max = math.pi
        scan.angle_increment = math.pi / 180.0
        scan.range_min = 0.1
        scan.range_max = 30.0
        scan.ranges = [float("inf")] * 361
        self.scan_pub.publish(scan)

        grid = OccupancyGrid()
        grid.header.stamp = stamp
        grid.header.frame_id = "map"
        grid.info.resolution = 0.05
        grid.info.width = 400
        grid.info.height = 400
        grid.info.origin.position.x = -10.0
        grid.info.origin.position.y = -10.0
        grid.info.origin.orientation.w = 1.0
        data = [0] * (grid.info.width * grid.info.height)
        wall_x = round((3.0 - grid.info.origin.position.x) / grid.info.resolution)
        y_min = round((-9.0 - grid.info.origin.position.y) / grid.info.resolution)
        y_max = round((9.0 - grid.info.origin.position.y) / grid.info.resolution)
        for y_index in range(y_min, y_max + 1):
            data[y_index * grid.info.width + wall_x] = 100
        grid.data = data
        self.map_pub.publish(grid)

    def wait_for_active(self):
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            self.publish_fixtures()
            rclpy.spin_once(self, timeout_sec=0.05)
            if not all(
                client.wait_for_service(timeout_sec=0.05)
                for client in self.lifecycle_states.values()
            ):
                continue
            states = []
            for client in self.lifecycle_states.values():
                future = client.call_async(GetState.Request())
                rclpy.spin_until_future_complete(self, future, timeout_sec=0.5)
                states.append(future.result())
            if all(
                state is not None and state.current_state.label == "active"
                for state in states
            ):
                return
        raise RuntimeError("Nav2 lifecycle nodes did not reach active state")

    def request_costmap_update(self):
        if not self.compute_path.wait_for_server(timeout_sec=5.0):
            raise RuntimeError("compute_path_to_pose action unavailable")
        goal = ComputePathToPose.Goal()
        goal.start = PoseStamped()
        goal.start.header.frame_id = "map"
        goal.start.pose.orientation.w = 1.0
        goal.goal = PoseStamped()
        goal.goal.header.frame_id = "map"
        goal.goal.pose.position.x = 1.0
        goal.goal.pose.orientation.w = 1.0
        goal.planner_id = "GridBased"
        future = self.compute_path.send_goal_async(goal)
        rclpy.spin_until_future_complete(self, future, timeout_sec=5.0)
        handle = future.result()
        if handle is None or not handle.accepted:
            raise RuntimeError("wall-clearance planner request rejected")
        result_future = handle.get_result_async()
        rclpy.spin_until_future_complete(self, result_future, timeout_sec=10.0)
        if result_future.result() is None:
            raise RuntimeError("wall-clearance planner request timed out")

    def wait_for_costmap(self):
        deadline = time.monotonic() + 30.0
        while time.monotonic() < deadline:
            self.publish_fixtures()
            rclpy.spin_once(self, timeout_sec=0.1)
            if (self.costmap is not None
                    and self.costmap.metadata.size_x > 0):
                return
        raise RuntimeError("global raw costmap was not published")

    def cost_at(self, x, y):
        metadata = self.costmap.metadata
        ix = round((x - metadata.origin.position.x) / metadata.resolution)
        iy = round((y - metadata.origin.position.y) / metadata.resolution)
        if (ix < 0 or iy < 0 or ix >= metadata.size_x
                or iy >= metadata.size_y):
            raise RuntimeError(f"costmap sample ({x},{y}) out of bounds")
        return self.costmap.data[iy * metadata.size_x + ix]

    def evaluate(self):
        wall = self.cost_at(3.0, 0.0)
        inflated_1m = self.cost_at(2.0, 0.0)
        inflated_1_3m = self.cost_at(1.7, 0.0)
        clear_1_6m = self.cost_at(1.4, 0.0)
        robot = self.cost_at(0.0, 0.0)
        print(
            "RESULT mode=wall_clearance "
            f"wall_cost={wall} inflated_1m={inflated_1m} "
            f"inflated_1_3m={inflated_1_3m} clear_1_6m={clear_1_6m} "
            f"robot_cost={robot} resolution={self.costmap.metadata.resolution:.3f}",
            flush=True,
        )
        if wall < 99:
            raise RuntimeError("wall was not represented as lethal cost")
        if inflated_1m <= 0 or inflated_1_3m <= 0:
            raise RuntimeError("inflation did not cover the configured clearance band")
        if clear_1_6m != 0:
            raise RuntimeError("inflation exceeded the configured 1.35 m radius")
        if robot != 0:
            raise RuntimeError("vehicle start pose was not clear of the wall")


def main():
    rclpy.init()
    node = WallClearanceProbe()
    try:
        node.wait_for_active()
        node.request_costmap_update()
        node.wait_for_costmap()
        node.evaluate()
    except RuntimeError as error:
        print(f"FAIL: {error}", file=sys.stderr, flush=True)
        return 1
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    print("PASS: Nav2 wall-clearance acceptance")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
