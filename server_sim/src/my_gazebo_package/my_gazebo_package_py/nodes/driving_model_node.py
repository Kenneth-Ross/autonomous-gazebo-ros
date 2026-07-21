#!/usr/bin/python3
import rclpy
from rclpy.node import Node
from std_msgs.msg import Float32
from geometry_msgs.msg import Twist, TwistStamped
from nav_msgs.msg import Odometry
import math

class DrivingModelNode(Node):
    def __init__(self):
        super().__init__('driving_model')

        # --- Parameters (Physics / Limits) ---
        self.declare_parameter('max_speed', 13.41) # 30 mph (~48.3 km/h)
        self.declare_parameter('max_accel', 30.0)  # Quick acceleration
        self.declare_parameter('max_decel', 25.0)
        self.declare_parameter('drag', 0.1)
        self.declare_parameter('auto_drive', False)

        # --- Parameters (Low-Level PID Control) ---
        self.declare_parameter('kp_vel', 1.2)
        self.declare_parameter('ki_vel', 0.1)
        self.declare_parameter('kd_vel', 0.05)
        self.declare_parameter('steering_slew_rate', 2.0) # radians per second

        # --- Parameters (Vehicle Geometry) ---
        self.declare_parameter('max_steering_angle', 0.6108)
        self.declare_parameter('max_velocity', 13.41) # 30 mph cap

        self.max_speed = min(self.get_parameter('max_speed').value, self.get_parameter('max_velocity').value)
        self.max_accel = self.get_parameter('max_accel').value
        self.max_decel = self.get_parameter('max_decel').value
        self.drag = self.get_parameter('drag').value
        self.max_steer_limit = self.get_parameter('max_steering_angle').value
        self.auto_drive = self.get_parameter('auto_drive').value
        self.kp_vel = self.get_parameter('kp_vel').value
        self.ki_vel = self.get_parameter('ki_vel').value
        self.kd_vel = self.get_parameter('kd_vel').value
        self.steering_slew_rate = self.get_parameter('steering_slew_rate').value
        self.cmd_timeout = 0.2 # seconds
        self.manual_override_timeout = 2.0 # seconds

        # --- State ---
        self.current_measured_vel = 0.0
        self.target_vel = 0.0
        self.vel_error_sum = 0.0
        self.last_vel_error = 0.0
        
        self.throttle = 1.0 if self.auto_drive else 0.0
        self.brake = 0.0
        self.target_steering_input = 0.0 # From commands (-1 to 1 normalized)
        self.current_steering_input = 0.0 # Actuator state (-1 to 1 normalized)
        
        self.last_time = self.get_clock().now()
        self.last_cmd_time = self.get_clock().now()
        self.last_manual_time = self.get_clock().now() - rclpy.time.Duration(seconds=self.manual_override_timeout)

        # --- Topics ---
        self.create_subscription(TwistStamped, '/car/control_request', self.control_request_cb, 10)
        self.create_subscription(Odometry, '/odometry/filtered', self.odom_cb, 10)
        self.create_subscription(Float32, '/car/throttle', self.throttle_cb, 10)
        self.create_subscription(Float32, '/car/brake', self.brake_cb, 10)
        self.create_subscription(Float32, '/car/steering', self.steering_cb, 10)
        
        # Publisher for Gazebo AckermannSteering plugin (via ros_gz_bridge)
        self.cmd_vel_pub = self.create_publisher(Twist, '/cmd_vel', 10)

        # --- Timers ---
        self.create_timer(0.05, self.update_loop)
        self.create_timer(2.0, self.status_report)

        self.get_logger().info('Driving Model Node (v11 - Closed-Loop & Watchdog Fix) started.')

    def odom_cb(self, msg):
        self.current_measured_vel = msg.twist.twist.linear.x

    def _is_manual_override_active(self):
        now = self.get_clock().now()
        age = (now - self.last_manual_time).nanoseconds / 1e9
        return age < self.manual_override_timeout

    def control_request_cb(self, msg):
        if self._is_manual_override_active():
            return # Ignore autonomous commands while under manual control
            
        self.target_vel = float(msg.twist.linear.x)
        self.target_steering_input = float(msg.twist.angular.z / self.max_steer_limit)
        self.target_steering_input = max(-1.0, min(1.0, self.target_steering_input))
        self.last_cmd_time = self.get_clock().now()

    def throttle_cb(self, msg):
        self.throttle = max(0.0, min(1.0, msg.data))
        self.last_manual_time = self.get_clock().now()
        self.last_cmd_time = self.get_clock().now()
        self.target_vel = 0.0 
        self.vel_error_sum = 0.0 # Reset integrator on manual takeover

    def brake_cb(self, msg):
        self.brake = max(0.0, min(1.0, msg.data))
        self.last_manual_time = self.get_clock().now()
        self.last_cmd_time = self.get_clock().now()
        self.target_vel = 0.0
        self.vel_error_sum = 0.0

    def steering_cb(self, msg):
        self.target_steering_input = max(-1.0, min(1.0, msg.data))
        self.last_manual_time = self.get_clock().now()
        self.last_cmd_time = self.get_clock().now()

    def status_report(self):
        self.get_logger().info(f'Heartbeat: V_msr={self.current_measured_vel:.2f}, V_tgt={self.target_vel:.2f}, Steer={self.current_steering_input:.2f}')

    def update_loop(self):
        now = self.get_clock().now()
        dt = (now - self.last_time).nanoseconds / 1e9
        self.last_time = now

        if dt <= 0.0 or dt > 0.5:
            return

        # --- Watchdog & Failsafe ---
        cmd_age = (now - self.last_cmd_time).nanoseconds / 1e9
        # Watchdog applies even in auto_drive if comms are lost
        if cmd_age > self.cmd_timeout:
            if self.throttle != 0.0 or self.brake != 1.0:
                self.get_logger().warn(f'WATCHDOG TRIGGERED: No commands for {cmd_age:.2f}s. Emergency Braking.')
            self.throttle = 0.0
            self.brake = 1.0
            self.target_steering_input = 0.0
            self.target_vel = 0.0
            self.vel_error_sum = 0.0 # CRITICAL: Reset integrator to prevent "kick" on reconnect
        
        # --- Steering Slew Rate Limiter ---
        steer_diff = self.target_steering_input - self.current_steering_input
        max_steer_change = (self.steering_slew_rate / self.max_steer_limit) * dt
        
        if abs(steer_diff) > max_steer_change:
            self.current_steering_input += math.copysign(max_steer_change, steer_diff)
        else:
            self.current_steering_input = self.target_steering_input

        # --- Closed-Loop Velocity Control (PID) ---
        # Only run PID if we have a non-zero target and aren't in manual override
        if abs(self.target_vel) > 0.01:
            vel_error = self.target_vel - self.current_measured_vel
            self.vel_error_sum += vel_error * dt
            self.vel_error_sum = max(-1.0, min(1.0, self.vel_error_sum)) # Anti-windup
            
            vel_deriv = (vel_error - self.last_vel_error) / dt
            self.last_vel_error = vel_error
            
            pid_out = (self.kp_vel * vel_error) + (self.ki_vel * self.vel_error_sum) + (self.kd_vel * vel_deriv)
            
            if pid_out > 0:
                self.throttle = max(0.0, min(1.0, pid_out))
                self.brake = 0.0
            else:
                self.throttle = 0.0
                self.brake = max(0.0, min(1.0, abs(pid_out)))
        elif cmd_age <= self.cmd_timeout:
             # Handle commanded stop
             if abs(self.current_measured_vel) > 0.05:
                 self.throttle = 0.0
                 self.brake = 0.8
                 self.vel_error_sum = 0.0
             else:
                 self.throttle = 0.0
                 self.brake = 0.5
                 self.vel_error_sum = 0.0

        # --- Physical Command Output ---
        tw = Twist()
        # The ECU now acts as a pure commander to the Gazebo Ackermann plugin
        # linear.x is the commanded velocity (simulating motor voltage/ESC output)
        # However, the Ackermann plugin in Gazebo expects actual target velocity (m/s)
        # In a real car, this would be raw motor PWM.
        # Since we are in simulation, we use the throttle/brake result to modulate speed.
        
        # Simple velocity-setpoint integrator for Gazebo:
        accel = self.throttle * self.max_accel
        decel = self.brake * self.max_decel
        drag = self.current_measured_vel * self.drag
        
        speed_cmd = self.current_measured_vel + (accel - decel - drag) * dt
        speed_cmd = max(0.0, min(self.max_speed, speed_cmd))

        tw.linear.x = float(speed_cmd)
        tw.angular.z = float(self.current_steering_input * self.max_steer_limit)
        
        self.cmd_vel_pub.publish(tw)

def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(DrivingModelNode())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
