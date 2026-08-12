#!/usr/bin/env python3
"""Legacy host-only orchestration utility."""

from rcl_interfaces.msg import Parameter, ParameterType
from rcl_interfaces.srv import SetParameters
import rclpy
from rclpy.node import Node
from ros_gz_interfaces.srv import SetEntityPose
from std_msgs.msg import String

try:
    from my_gazebo_package.srv import ChangeTrack, StartRun
except ImportError:  # host-only service package is absent from edge workspace
    ChangeTrack = None
    StartRun = None


class TestOrchestratorNode(Node):
    """Reset host simulation and apply legacy pursuit parameters."""

    def __init__(self):
        super().__init__('test_orchestrator_node')

        self.track_client = (
            self.create_client(ChangeTrack, '/change_track')
            if ChangeTrack is not None else None)
        self.pose_client = self.create_client(
            SetEntityPose, '/world/default/set_pose')
        self.pp_param_client = self.create_client(
            SetParameters, '/pure_pursuit_node/set_parameters')

        if StartRun is not None:
            self.create_service(
                StartRun, '/orchestrator/start_run', self.start_run_cb)
        else:
            self.get_logger().warning(
                'my_gazebo_package services unavailable; '
                'host-only start service disabled')

        self.create_subscription(
            String, '/racing/failure', self.failure_cb, 10)
        self.get_logger().info(
            'Test orchestrator node started; waiting for '
            '/orchestrator/start_run calls.')

    def set_pp_params(self, speed, lookahead):
        """Set legacy pursuit parameters when node is available."""
        request = SetParameters.Request()

        speed_parameter = Parameter()
        speed_parameter.name = 'target_speed'
        speed_parameter.value.type = ParameterType.PARAMETER_DOUBLE
        speed_parameter.value.double_value = float(speed)

        lookahead_parameter = Parameter()
        lookahead_parameter.name = 'lookahead_distance'
        lookahead_parameter.value.type = ParameterType.PARAMETER_DOUBLE
        lookahead_parameter.value.double_value = float(lookahead)

        request.parameters = [speed_parameter, lookahead_parameter]
        self.pp_param_client.call_async(request)

    def set_car_pose(self, _spawn_dict):
        """Reset simulated vehicle pose to known origin."""
        request = SetEntityPose.Request()
        request.entity.name = 'my_robot'
        request.pose.position.x = 0.0
        request.pose.position.y = 0.0
        request.pose.position.z = 0.5
        self.pose_client.call_async(request)

    async def start_run_cb(self, request, response):
        """Apply track, pursuit, and pose settings for a legacy run."""
        self.get_logger().info(
            f'Starting run: track={request.track_name}, '
            f'speed={request.target_speed}, lookahead={request.lookahead}')

        if (self.track_client is not None and
                self.track_client.wait_for_service(timeout_sec=2.0)):
            track_request = ChangeTrack.Request()
            track_request.track_name = request.track_name
            await self.track_client.call_async(track_request)

        if self.pp_param_client.wait_for_service(timeout_sec=2.0):
            self.set_pp_params(request.target_speed, request.lookahead)

        if self.pose_client.wait_for_service(timeout_sec=2.0):
            self.set_car_pose(None)

        response.success = True
        response.message = 'Run started successfully'
        return response

    def failure_cb(self, msg):
        """Log validator failure for legacy orchestration."""
        self.get_logger().warning(
            f'Orchestrator received failure: {msg.data}')


def main(args=None):
    """Run legacy orchestration utility."""
    rclpy.init(args=args)
    node = TestOrchestratorNode()
    rclpy.spin(node)
    node.destroy_node()
    rclpy.shutdown()


if __name__ == '__main__':
    main()
