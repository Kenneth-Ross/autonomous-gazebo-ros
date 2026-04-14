#!/usr/bin/python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from geometry_msgs.msg import Twist
import math

class DrivingModelNode(Node):
    def __init__(self):
        super().__init__('driving_model')

        # --- Parameters (Physics / Limits) ---
        self.declare_parameter('max_speed', 15.0)
        self.declare_parameter('max_accel', 20.0)
        self.declare_parameter('max_decel', 20.0)
        self.declare_parameter('drag', 0.1)
        self.declare_parameter('auto_drive', True)

        # --- Parameters (Vehicle Geometry for logic) ---
        self.declare_parameter('max_steering_angle', 0.6108)
        self.declare_parameter('max_velocity', 1.0) # Model physical limit

        self.max_speed = min(self.get_parameter('max_speed').value, self.get_parameter('max_velocity').value)
        self.max_accel = self.get_parameter('max_accel').value
        self.max_decel = self.get_parameter('max_decel').value
        self.drag = self.get_parameter('drag').value
        self.max_steer_limit = self.get_parameter('max_steering_angle').value
        self.auto_drive = self.get_parameter('auto_drive').value

        # --- State ---
        self.velocity_setpoint = 0.0
        self.throttle = 1.0 if self.auto_drive else 0.0
        self.brake = 0.0
        self.steering_input = 0.0 # -1.0 to 1.0
        self.last_time = self.get_clock().now()

        # --- Topics ---
        self.create_subscription(Float32, '/car/throttle', self.throttle_cb, 10)
        self.create_subscription(Float32, '/car/brake', self.brake_cb, 10)
        self.create_subscription(Float32, '/car/steering', self.steering_cb, 10)
        
        # Publisher for Gazebo AckermannSteering plugin (via ros_gz_bridge)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # --- Timers ---
        self.create_timer(0.05, self.update_loop)
        self.create_timer(2.0, self.status_report)

        self.get_logger().info('Driving Model Node (v6 - Ackermann Plugin Bridge) started.')

    def throttle_cb(self, msg): self.throttle = max(0.0, min(1.0, msg.data))
    def brake_cb(self, msg):    self.brake = max(0.0, min(1.0, msg.data))
    def steering_cb(self, msg): self.steering_input = max(-1.0, min(1.0, msg.data))

    def status_report(self):
        self.get_logger().info(f'Heartbeat: Throttle={self.throttle:.2f}, Velocity={self.velocity_setpoint:.2f}')

    def update_loop(self):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now

        if dt <= 0.0 or dt > 0.5:
            return

        # --- Physics Update ---
        accel = self.throttle * self.max_accel
        decel = self.brake * self.max_decel
        drag = self.velocity_setpoint * self.drag
        
        self.velocity_setpoint += (accel - decel - drag) * dt
        self.velocity_setpoint = max(0.0, min(self.max_speed, self.velocity_setpoint))

        # --- Control Output ---
        tw = Twist()
        # Ackermann Plugin expects linear.x as speed (m/s)
        tw.linear.x = float(self.velocity_setpoint)
        # Ackermann Plugin expects angular.z as steering angle (radians)
        tw.angular.z = float(self.steering_input * self.max_steer_limit)
        
        self.cmd_vel_pub.publish(tw)

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(DrivingModelNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
