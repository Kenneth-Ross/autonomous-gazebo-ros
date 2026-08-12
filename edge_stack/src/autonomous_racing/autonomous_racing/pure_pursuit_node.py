#!/usr/bin/env python3
"""Typed racing-path pursuit candidate producer."""

import math

from autonomous_racing_msgs.msg import ControlCandidate, RacingPath
from nav_msgs.msg import Odometry
import rclpy
from rclpy.node import Node


class PurePursuitNode(Node):
    """Consume typed map/base paths and publish bounded candidates only."""

    def __init__(self):
        super().__init__('pure_pursuit_node')
        self.declare_parameter('lookahead_distance', 3.0)
        self.declare_parameter('lookahead_gain', 0.5)
        self.declare_parameter('target_speed', 2.0)
        self.declare_parameter('min_lookahead', 1.5)
        self.declare_parameter('max_lookahead', 8.0)
        self.declare_parameter('wheelbase', 1.511)
        self.declare_parameter('max_steering', 0.6108)
        self.path = None
        self.current_pose = None
        self.current_velocity = 0.0
        self.create_subscription(
            RacingPath, '/racing/local_path', self.path_cb, 10)
        self.create_subscription(Odometry, '/odom', self.odom_cb, 10)
        self.control_pub = self.create_publisher(
            ControlCandidate, '/racing/control_candidate', 10)
        self.create_timer(0.05, self.control_loop)

    def path_cb(self, message):
        self.path = message

    def odom_cb(self, message):
        self.current_pose = message.pose.pose
        self.current_velocity = message.twist.twist.linear.x

    @staticmethod
    def get_yaw_from_pose(pose):
        q = pose.orientation
        siny_cosp = 2 * (q.w * q.z + q.x * q.y)
        cosy_cosp = 1 - 2 * (q.y * q.y + q.z * q.z)
        return math.atan2(siny_cosp, cosy_cosp)

    @staticmethod
    def get_distance(x1, y1, x2, y2):
        return math.hypot(x1 - x2, y1 - y2)

    def find_goal_point(self, lookahead, car_x, car_y):
        if self.path is None or not self.path.points:
            return None
        closest_idx = min(
            range(len(self.path.points)),
            key=lambda index: self.get_distance(
                car_x, car_y, self.path.points[index].pose.position.x,
                self.path.points[index].pose.position.y))
        for index in range(closest_idx, len(self.path.points)):
            point = self.path.points[index]
            distance = self.get_distance(
                car_x, car_y, point.pose.position.x, point.pose.position.y)
            if distance >= lookahead:
                return point
        return self.path.points[-1]

    def publish_invalid(self, reason):
        message = ControlCandidate()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'base_link'
        message.valid = False
        message.fault_reason = reason
        self.control_pub.publish(message)

    def control_loop(self):
        if self.current_pose is None or self.path is None:
            self.publish_invalid('path_or_odometry_missing')
            return
        if not self.path.points:
            self.publish_invalid('path_empty')
            return

        lookahead_base = self.get_parameter('lookahead_distance').value
        lookahead_gain = self.get_parameter('lookahead_gain').value
        min_lookahead = self.get_parameter('min_lookahead').value
        max_lookahead = self.get_parameter('max_lookahead').value
        default_speed = self.get_parameter('target_speed').value
        wheelbase = self.get_parameter('wheelbase').value
        max_steering = self.get_parameter('max_steering').value
        lookahead = max(
            min_lookahead,
            min(max_lookahead, lookahead_base +
                lookahead_gain * abs(self.current_velocity)))

        is_local = self.path.header.frame_id in ('base_link', 'ackermann_car')
        car_x = 0.0 if is_local else self.current_pose.position.x
        car_y = 0.0 if is_local else self.current_pose.position.y
        car_yaw = 0.0 if is_local else self.get_yaw_from_pose(self.current_pose)
        point = self.find_goal_point(lookahead, car_x, car_y)
        if point is None or point.state == point.UNSAFE:
            self.publish_invalid('path_unsafe')
            return

        dx = point.pose.position.x - car_x
        dy = point.pose.position.y - car_y
        alpha = math.atan2(dy, dx) - car_yaw
        alpha = math.atan2(math.sin(alpha), math.cos(alpha))
        steering = math.atan2(2.0 * wheelbase * math.sin(alpha), lookahead)
        steering = max(-max_steering, min(max_steering, steering))

        message = ControlCandidate()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'base_link'
        message.speed = max(0.0, float(point.target_speed or default_speed))
        message.steering = float(steering)
        message.path_revision = self.path.revision
        message.confidence = float(point.confidence)
        message.valid = True
        self.control_pub.publish(message)


def main(args=None):
    rclpy.init(args=args)
    node = PurePursuitNode()
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
