import time

from edge_nav2.nav2_ackermann_bridge import Nav2AckermannBridge
from geometry_msgs.msg import Twist, TwistStamped
import pytest
import rclpy
from rclpy.executors import SingleThreadedExecutor


def spin_until(executor, predicate, timeout=1.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        executor.spin_once(timeout_sec=0.02)
        if predicate():
            return True
    return False


def test_bridge_runtime_publishes_bounded_ackermann_requests_at_20_hz():
    rclpy.init()
    bridge = Nav2AckermannBridge()
    observer = rclpy.create_node('ackermann_bridge_runtime_test')
    publisher = observer.create_publisher(Twist, '/nav_cmd_vel', 10)
    received = []
    observer.create_subscription(
        TwistStamped,
        '/car/control_request',
        lambda msg: received.append((time.monotonic(), msg)),
        10,
    )
    executor = SingleThreadedExecutor()
    executor.add_node(bridge)
    executor.add_node(observer)

    try:
        command = Twist()
        command.linear.x = 1.0
        command.angular.z = 0.5
        publisher.publish(command)
        assert spin_until(executor, lambda: len(received) >= 5)

        stamps = [stamp for stamp, _ in received[-5:]]
        intervals = [current - previous for previous, current in zip(
            stamps, stamps[1:])]
        output = received[-1][1]
        assert output.header.frame_id == 'base_link'
        assert output.twist.linear.x == pytest.approx(1.0)
        assert output.twist.angular.z == pytest.approx(0.6108)
        assert sum(intervals) / len(intervals) == pytest.approx(0.05, abs=0.02)

        received.clear()
        command.linear.x = -0.05
        command.angular.z = -0.5
        publisher.publish(command)
        assert spin_until(
            executor,
            lambda: received and received[-1][1].twist.angular.z < 0.0,
        )
        assert received[-1][1].twist.angular.z == pytest.approx(-0.6108)
    finally:
        executor.remove_node(observer)
        executor.remove_node(bridge)
        observer.destroy_node()
        bridge.destroy_node()
        executor.shutdown()
        if rclpy.ok():
            rclpy.shutdown()
