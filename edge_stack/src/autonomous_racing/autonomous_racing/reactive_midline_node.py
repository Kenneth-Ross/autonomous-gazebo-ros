#!/usr/bin/env python3
"""Build a conservative rolling typed path from visible cone landmarks."""

import math

from autonomous_racing_msgs.msg import RacingPath, RacingPathPoint
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node
from std_msgs.msg import String
from visualization_msgs.msg import MarkerArray


class ReactiveMidlineNode(Node):
    """Publish rolling path evidence; never invent path without cone geometry."""

    def __init__(self):
        super().__init__('reactive_midline_node')
        self.declare_parameter('fov_distance', 15.0)
        self.declare_parameter('fov_angle', 1.0)
        self.declare_parameter('track_width', 6.0)
        self.declare_parameter('exploration_speed', 2.0)
        self.current_pose = None
        self.cones = []
        self.phase = 'exploring'
        self.revision = 0
        self.create_subscription(
            MarkerArray, '/rtabmap/landmarks', self.landmarks_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(String, '/racing/phase', self.phase_cb, 10)
        self.path_pub = self.create_publisher(
            RacingPath, '/racing/local_path', 10)
        self.create_timer(0.1, self.compute_midline)

    def phase_cb(self, message):
        self.phase = message.data

    def odom_cb(self, message):
        self.current_pose = message.pose.pose

    def landmarks_cb(self, message):
        if self.phase != 'exploring':
            return
        self.cones = [
            (marker.pose.position.x, marker.pose.position.y)
            for marker in message.markers
        ]

    @staticmethod
    def get_yaw_from_pose(pose):
        q = pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def transform_to_local(cx, cy, rx, ry, ryaw):
        dx = cx - rx
        dy = cy - ry
        return (
            dx * math.cos(-ryaw) - dy * math.sin(-ryaw),
            dx * math.sin(-ryaw) + dy * math.cos(-ryaw),
        )

    def append_point(self, path, x, y, confidence, state):
        point = RacingPathPoint()
        point.pose.position.x = float(x)
        point.pose.position.y = float(y)
        point.pose.orientation.w = 1.0
        point.target_speed = float(self.get_parameter('exploration_speed').value)
        point.confidence = float(confidence)
        point.observation_support = float(confidence)
        point.pose_quality = float(confidence)
        point.corridor_geometry = float(confidence)
        point.continuity = float(confidence)
        point.recency = float(confidence)
        point.localization = 1.0
        point.state = state
        path.points.append(point)

    def empty_path(self):
        path = RacingPath()
        path.header.stamp = self.get_clock().now().to_msg()
        path.header.frame_id = 'base_link'
        path.revision = self.revision
        path.mode = RacingPath.ROLLING
        path.closed_loop = False
        return path

    def compute_midline(self):
        self.revision += 1
        path = self.empty_path()
        if self.current_pose is None or self.phase != 'exploring':
            self.path_pub.publish(path)
            return

        rx = self.current_pose.position.x
        ry = self.current_pose.position.y
        ryaw = self.get_yaw_from_pose(self.current_pose)
        fov_dist = float(self.get_parameter('fov_distance').value)
        fov_angle = float(self.get_parameter('fov_angle').value)
        left_cones = []
        right_cones = []
        for cx, cy in self.cones:
            lx, ly = self.transform_to_local(cx, cy, rx, ry, ryaw)
            if lx <= 0.0 or math.hypot(lx, ly) >= fov_dist:
                continue
            if abs(math.atan2(ly, lx)) >= fov_angle:
                continue
            (left_cones if ly > 0.0 else right_cones).append((lx, ly))
        left_cones.sort(key=lambda cone: cone[0])
        right_cones.sort(key=lambda cone: cone[0])

        max_pairs = max(len(left_cones), len(right_cones))
        half_width = float(self.get_parameter('track_width').value) / 2.0
        for index in range(max_pairs):
            left = left_cones[index] if index < len(left_cones) else None
            right = right_cones[index] if index < len(right_cones) else None
            if left is not None and right is not None:
                self.append_point(
                    path, (left[0] + right[0]) / 2.0,
                    (left[1] + right[1]) / 2.0, 0.75, RacingPathPoint.TRUSTED)
            elif left is not None:
                self.append_point(
                    path, left[0], left[1] - half_width, 0.45,
                    RacingPathPoint.DEGRADED)
            elif right is not None:
                self.append_point(
                    path, right[0], right[1] + half_width, 0.45,
                    RacingPathPoint.DEGRADED)
        self.path_pub.publish(path)


def main(args=None):
    rclpy.init(args=args)
    node = ReactiveMidlineNode()
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
