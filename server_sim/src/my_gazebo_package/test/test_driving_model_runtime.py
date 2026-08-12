import time
import unittest

from geometry_msgs.msg import Twist, TwistStamped
import launch
import launch_ros.actions
import launch_testing.actions
import launch_testing.asserts
from nav_msgs.msg import Odometry
import pytest
import rclpy
from std_msgs.msg import Float32


@pytest.mark.launch_test
def generate_test_description():
    driving_model = launch_ros.actions.Node(
        package='my_gazebo_package',
        executable='driving_model_node.py',
        parameters=[{
            'auto_drive': False,
            'max_accel': 30.0,
            'max_decel': 25.0,
            'steering_slew_rate': 2.0,
            'max_steering_angle': 0.6108,
        }],
        output='screen',
    )
    return (
        launch.LaunchDescription([
            driving_model,
            launch_testing.actions.ReadyToTest(),
        ]),
        {'driving_model': driving_model},
    )


class TestDrivingModelRuntime(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('driving_model_acceptance_test')
        self.control_pub = self.node.create_publisher(
            TwistStamped, '/car/control_request', 10)
        self.odom_pub = self.node.create_publisher(
            Odometry, '/odometry/filtered', 10)
        self.brake_pub = self.node.create_publisher(Float32, '/car/brake', 10)
        self.outputs = []
        self.node.create_subscription(Twist, '/cmd_vel', self._output_cb, 10)
        self._spin_for(0.5)

    def tearDown(self):
        self.node.destroy_node()

    def _output_cb(self, msg):
        self.outputs.append((time.monotonic(), msg.linear.x, msg.angular.z))

    def _spin_for(self, duration, tick=None):
        deadline = time.monotonic() + duration
        while time.monotonic() < deadline:
            if tick is not None:
                tick()
            rclpy.spin_once(self.node, timeout_sec=0.01)

    def _publish_odom(self, velocity):
        msg = Odometry()
        msg.twist.twist.linear.x = velocity
        self.odom_pub.publish(msg)

    def _publish_control(self, velocity, steering=0.0):
        msg = TwistStamped()
        msg.twist.linear.x = velocity
        msg.twist.angular.z = steering
        self.control_pub.publish(msg)

    def test_safety_and_actuator_runtime_contract(self):
        def publish_fast_request():
            self._publish_odom(5.0)
            self._publish_control(10.0)

        self._spin_for(0.35, publish_fast_request)
        self.assertTrue(any(speed > 5.5 for _, speed, _ in self.outputs))

        self.outputs.clear()
        last_command = time.monotonic()
        self._publish_control(10.0)
        self._spin_for(0.35, lambda: self._publish_odom(5.0))
        braking_times = [
            stamp - last_command for stamp, speed, _ in self.outputs
            if speed < 4.5
        ]
        self.assertTrue(braking_times, 'watchdog never commanded emergency braking')
        self.assertGreaterEqual(braking_times[0], 0.18)
        self.assertLessEqual(braking_times[0], 0.27)

        brake = Float32()
        brake.data = 1.0
        self.brake_pub.publish(brake)
        self.outputs.clear()

        def publish_ignored_request():
            self._publish_odom(0.0)
            self._publish_control(10.0)

        self._spin_for(1.8, publish_ignored_request)
        self.assertFalse(any(speed > 0.01 for _, speed, _ in self.outputs))
        self._spin_for(0.3, publish_ignored_request)
        self.assertTrue(any(speed > 0.1 for _, speed, _ in self.outputs))

        def publish_left_lock():
            self._publish_odom(0.0)
            self._publish_control(0.0, -0.6108)

        self._spin_for(0.75, publish_left_lock)
        self.outputs.clear()
        reversal_start = time.monotonic()

        def publish_right_lock():
            self._publish_odom(0.0)
            self._publish_control(0.0, 0.6108)

        self._spin_for(0.75, publish_right_lock)
        steering = [(stamp, angle) for stamp, _, angle in self.outputs]
        self.assertTrue(steering)
        first_right_lock = next(
            (stamp for stamp, angle in steering if angle >= 0.60), None)
        self.assertIsNotNone(first_right_lock, 'steering never reached right lock')
        self.assertGreaterEqual(first_right_lock - reversal_start, 0.54)
        for (_, previous), (_, current) in zip(steering, steering[1:]):
            self.assertLessEqual(abs(current - previous), 0.13)


@launch_testing.post_shutdown_test()
class TestDrivingModelShutdown(unittest.TestCase):
    def test_clean_exit(self, proc_info, driving_model):
        launch_testing.asserts.assertExitCodes(proc_info)
