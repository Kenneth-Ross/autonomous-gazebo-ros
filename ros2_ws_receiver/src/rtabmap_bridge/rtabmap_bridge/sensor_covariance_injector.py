#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from sensor_msgs.msg import Imu
from rclpy.qos import qos_profile_sensor_data

class SensorCovarianceInjector(Node):
    def __init__(self):
        super().__init__('sensor_covariance_injector')
        
        # Odom subscriber and publisher
        self.odom_sub = self.create_subscription(
            Odometry,
            '/odom',
            self.odom_callback,
            qos_profile_sensor_data
        )
        self.odom_pub = self.create_publisher(
            Odometry,
            '/odom/filtered_input',
            qos_profile_sensor_data
        )
        
        # IMU subscriber and publisher
        self.imu_sub = self.create_subscription(
            Imu,
            '/imu',
            self.imu_callback,
            qos_profile_sensor_data
        )
        self.imu_pub = self.create_publisher(
            Imu,
            '/imu/filtered_input',
            qos_profile_sensor_data
        )
        
        self.get_logger().info('Sensor Covariance Injector started.')

    def odom_callback(self, msg: Odometry):
        # Default all to large variance (untrusted)
        msg.pose.covariance = [1e6] * 36
        msg.twist.covariance = [1e6] * 36
        
        # Inject Pose Covariance (Position X,Y: 0.05, Yaw: 0.1)
        msg.pose.covariance[0] = 0.05  # X
        msg.pose.covariance[7] = 0.05  # Y
        msg.pose.covariance[35] = 0.1  # Yaw
        
        # Inject Twist Covariance (Vel X,Y: 0.02, Yaw Vel: 0.05)
        msg.twist.covariance[0] = 0.02  # X vel
        msg.twist.covariance[7] = 0.02  # Y vel
        msg.twist.covariance[35] = 0.05 # Yaw vel
        
        self.odom_pub.publish(msg)

    def imu_callback(self, msg: Imu):
        # Default all to large variance (untrusted)
        msg.orientation_covariance = [1e6] * 9
        msg.angular_velocity_covariance = [1e6] * 9
        msg.linear_acceleration_covariance = [1e6] * 9
        
        # Orientation Covariance (Yaw: 0.01)
        msg.orientation_covariance[8] = 0.01
        
        # Angular Velocity Covariance (Yaw: 0.005)
        msg.angular_velocity_covariance[8] = 0.005
        
        # Linear Acceleration Covariance (X: 0.1)
        msg.linear_acceleration_covariance[0] = 0.1
        
        self.imu_pub.publish(msg)

def main(args=None):
    rclpy.init(args=args)
    node = SensorCovarianceInjector()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()
