#!/usr/bin/env python3
from edge_nav2.ackermann_kinematics import bounded_yaw_rate, steering_angle
from geometry_msgs.msg import Twist, TwistStamped
import rclpy
from rclpy._rclpy_pybind11 import RCLError
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


class Nav2AckermannBridge(Node):
    def __init__(self):
        super().__init__('nav2_ackermann_bridge')

        self.declare_parameter('wheelbase', 1.511)
        self.declare_parameter('min_velocity', 0.1)
        self.declare_parameter('max_steering_angle', 0.6108)

        self.L = self.get_parameter('wheelbase').value
        self.min_vel = self.get_parameter('min_velocity').value
        self.max_steering_angle = (
            self.get_parameter('max_steering_angle').value)

        self.target_vel = 0.0
        self.target_omega = 0.0

        self.create_subscription(Twist, '/nav_cmd_vel', self.nav_cmd_cb, 10)
        self.control_pub = self.create_publisher(
            TwistStamped, '/car/control_request', 10)
        self.create_timer(0.05, self.control_loop)

        self.get_logger().info(
            'Nav2 Ackermann Bridge (v3 - High-Level Brain) started.')

    def nav_cmd_cb(self, msg):
        self.target_vel = msg.linear.x
        self.target_omega = msg.angular.z

    def control_loop(self):
        limited_omega = bounded_yaw_rate(
            self.target_vel, self.target_omega, self.L,
            self.max_steering_angle, self.min_vel,
        )
        target_steering = steering_angle(
            self.target_vel, limited_omega, self.L, self.min_vel,
            self.max_steering_angle,
        )

        msg = TwistStamped()
        msg.header.stamp = self.get_clock().now().to_msg()
        msg.header.frame_id = 'base_link'
        msg.twist.linear.x = float(self.target_vel)
        msg.twist.angular.z = float(target_steering)
        self.control_pub.publish(msg)


def main(args=None):
    rclpy.init(args=args)
    node = Nav2AckermannBridge()
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException, RCLError):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()
