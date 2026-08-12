#!/usr/bin/env python3
"""Ground-truth-only race validator for simulation acceptance."""

import json
import math
import time

from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
import rclpy
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node
from std_msgs.msg import Float32, Int32, String
from tf2_msgs.msg import TFMessage
from visualization_msgs.msg import MarkerArray


class RaceValidatorNode(Node):
    """Report simulation-only lap progress and failure evidence."""

    def __init__(self):
        super().__init__('race_validator_node')

        self.declare_parameter('stall_timeout', 10.0)
        self.declare_parameter('track_width', 6.0)

        self.centerline = []
        self.gt_car_pose = None
        self.est_car_pose = None
        self.current_vel = 0.0

        self.lap_progress = 0.0
        self.laps_completed = 0
        self.last_progress_time = time.time()
        self.max_progress_seen = 0.0
        self.status = 'running'
        self.start_time = time.time()

        self.failure_pub = self.create_publisher(
            String, '/racing/failure', 10)
        self.progress_pub = self.create_publisher(
            Float32, '/racing/lap_progress', 10)
        self.lap_pub = self.create_publisher(
            Int32, '/racing/lap_complete', 10)
        self.status_pub = self.create_publisher(
            String, '/racing/run_status', 10)

        self.create_subscription(
            TFMessage, '/ground_truth/tf', self.gt_tf_cb, 10)
        self.create_subscription(
            MarkerArray, '/ground_truth/cones', self.gt_cones_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.create_subscription(Twist, '/cmd_vel', self.cmd_vel_cb, 10)

        self.create_timer(0.1, self.validation_loop)
        self.get_logger().info('Race validator node started.')

    def gt_tf_cb(self, msg):
        """Track simulation ground-truth vehicle pose."""
        for transform in msg.transforms:
            if transform.child_frame_id in ('ackermann_car', 'my_robot'):
                self.gt_car_pose = (
                    transform.transform.translation.x,
                    transform.transform.translation.y,
                )

    def gt_cones_cb(self, msg):
        """Build one evaluation-only centerline from ground-truth markers."""
        if self.centerline or not msg.markers:
            return

        markers = msg.markers
        num_pairs = len(markers) // 2
        inner = [
            (marker.pose.position.x, marker.pose.position.y)
            for marker in markers[:num_pairs]
        ]
        outer = [
            (marker.pose.position.x, marker.pose.position.y)
            for marker in markers[num_pairs:2 * num_pairs]
        ]
        for first, second in zip(inner, outer):
            self.centerline.append((
                (first[0] + second[0]) / 2.0,
                (first[1] + second[1]) / 2.0,
            ))

        self.get_logger().info(
            f'Validator extracted {len(self.centerline)} centerline points.')

    def odom_cb(self, msg):
        """Track estimated pose and longitudinal velocity for diagnostics."""
        self.est_car_pose = (
            msg.pose.pose.position.x,
            msg.pose.pose.position.y,
        )
        self.current_vel = msg.twist.twist.linear.x

    def cmd_vel_cb(self, _msg):
        """Keep legacy command subscription for validator compatibility."""

    def get_closest_centerline_index(self):
        """Return closest ground-truth centerline point and distance."""
        if not self.centerline or not self.gt_car_pose:
            return -1, float('inf')

        min_dist = float('inf')
        closest_idx = -1
        for index, point in enumerate(self.centerline):
            distance = math.sqrt(
                (point[0] - self.gt_car_pose[0]) ** 2 +
                (point[1] - self.gt_car_pose[1]) ** 2)
            if distance < min_dist:
                min_dist = distance
                closest_idx = index

        return closest_idx, min_dist

    def validation_loop(self):
        """Publish progress and latch evaluation failures."""
        if self.status != 'running':
            return

        status_msg = String()
        status_msg.data = self.status
        self.status_pub.publish(status_msg)

        if not self.centerline or not self.gt_car_pose:
            return

        index, distance_to_center = self.get_closest_centerline_index()
        progress = index / len(self.centerline)

        if self.lap_progress > 0.9 and progress < 0.1:
            self.laps_completed += 1
            self.lap_pub.publish(Int32(data=self.laps_completed))
            self.get_logger().info(
                f'Lap {self.laps_completed} completed.')
            self.max_progress_seen = 0.0

        self.lap_progress = progress
        self.progress_pub.publish(Float32(data=self.lap_progress))

        if progress > self.max_progress_seen + 0.02:
            self.max_progress_seen = progress
            self.last_progress_time = time.time()

        stall_timeout = self.get_parameter('stall_timeout').value
        track_width = self.get_parameter('track_width').value
        failure_type = None
        if distance_to_center > track_width / 2.0:
            failure_type = 'track_departure'
        elif time.time() - self.last_progress_time > stall_timeout:
            failure_type = 'stall_timeout'

        if not failure_type:
            return

        self.status = 'failed'
        self.get_logger().warning(f'Race failed: {failure_type}')
        failure = {
            'failure_type': failure_type,
            'failure_time': time.time() - self.start_time,
            'failure_pose': {
                'x': self.gt_car_pose[0],
                'y': self.gt_car_pose[1],
            },
            'failure_velocity': self.current_vel,
            'laps_completed': self.laps_completed,
            'lap_progress_at_failure': self.lap_progress,
            'duration_seconds': time.time() - self.start_time,
        }
        failure_msg = String()
        failure_msg.data = json.dumps(failure)
        self.failure_pub.publish(failure_msg)

        status_msg.data = self.status
        self.status_pub.publish(status_msg)


def main(args=None):
    """Run the simulation-only validator."""
    rclpy.init(args=args)
    node = RaceValidatorNode()
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
