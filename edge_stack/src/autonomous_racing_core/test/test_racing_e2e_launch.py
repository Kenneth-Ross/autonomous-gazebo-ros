"""Production control graph acceptance; fixtures stop at sensor/recorder inputs."""

import math
import time
import unittest

from autonomous_racing_msgs.msg import (ConeEstimate, ConeMap, ControlCandidate,
                                        RacingPath, RecorderHeartbeat,
                                        SupervisorStatus)
from autonomous_racing_msgs.srv import AbortRun, PrepareRun, StartRun
from builtin_interfaces.msg import Time
from geometry_msgs.msg import TransformStamped, TwistStamped
import launch
import launch_ros.actions
import launch_testing
import launch_testing.asserts
from nav_msgs.msg import Odometry
import pytest
import rclpy
from tf2_ros.static_transform_broadcaster import StaticTransformBroadcaster
from visualization_msgs.msg import Marker, MarkerArray


@pytest.mark.launch_test
def generate_test_description():
    nodes = [launch_ros.actions.Node(
        package='autonomous_racing_core', executable=executable,
        name=name, output='screen') for executable, name in (
            ('racing_supervisor_node', 'e2e_supervisor'),
            ('racing_planner_node', 'e2e_planner'),
            ('racing_controller_node', 'e2e_controller'),
            ('cone_map_adapter_node', 'e2e_marker_adapter'))]
    return launch.LaunchDescription([
        *nodes, launch_testing.actions.ReadyToTest()]), {'nodes': nodes}


class TestRacingE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('racing_e2e_fixture')
        self.commands, self.statuses, self.paths, self.candidates, self.maps = (
            [], [], [], [], [])
        self.node.create_subscription(
            TwistStamped, '/car/control_request', self.commands.append, 50)
        self.node.create_subscription(
            SupervisorStatus, '/racing/supervisor_status', self.statuses.append, 50)
        self.node.create_subscription(
            RacingPath, '/racing/local_path', self.paths.append, 50)
        self.node.create_subscription(
            ControlCandidate, '/racing/control_candidate', self.candidates.append, 50)
        self.node.create_subscription(
            ConeMap, '/racing/cone_map', self.maps.append, 50)
        self.map_pub = self.node.create_publisher(ConeMap, '/racing/cone_map', 10)
        self.odom_pub = self.node.create_publisher(Odometry, '/odometry/filtered', 10)
        self.heartbeat_pub = self.node.create_publisher(
            RecorderHeartbeat, '/racing/recorder/heartbeat', 10)
        # Used only for adversarial injection; nominal candidates come from C++.
        self.fault_pub = self.node.create_publisher(
            ControlCandidate, '/racing/control_candidate', 10)
        self.marker_pub = self.node.create_publisher(
            MarkerArray, '/rtabmap/landmarks', 10)
        self.prepare_client = self.node.create_client(PrepareRun, '/racing/prepare')
        self.start_client = self.node.create_client(StartRun, '/racing/start')
        self.abort_client = self.node.create_client(AbortRun, '/racing/abort')
        self.tf = StaticTransformBroadcaster(self.node)
        for child in ('base_link', 'odom'):
            transform = TransformStamped()
            transform.header.stamp = self.now()
            transform.header.frame_id = 'map'
            transform.child_frame_id = child
            transform.transform.translation.x = 10.0
            transform.transform.translation.y = 20.0
            transform.transform.rotation.z = math.sin(math.pi / 4)
            transform.transform.rotation.w = math.cos(math.pi / 4)
            self.tf.sendTransform(transform)
        self.run_id = 'not-prepared'
        self.sequence = 0
        self.map_mode = self.odom_mode = self.heartbeat_mode = 'nominal'
        self.next_feed = 0.0
        for client in (self.prepare_client, self.start_client, self.abort_client):
            self.assertTrue(client.wait_for_service(timeout_sec=10.0))

    def tearDown(self):
        self.node.destroy_node()

    def now(self):
        return self.node.get_clock().now().to_msg()

    def feed(self):
        if time.monotonic() < self.next_feed:
            return
        self.next_feed = time.monotonic() + 0.02
        if self.map_mode != 'off':
            message = ConeMap()
            message.header.stamp = self.now()
            message.header.frame_id = 'missing_map' if self.map_mode == 'missing_tf' else 'map'
            message.localization_confidence = {
                'unlocalized': 0.0, 'unsafe': 0.2}.get(self.map_mode, 1.0)
            self.sequence += 1
            message.map_revision = self.sequence
            coordinates = [(3.0, 2.0), (6.0, 2.0), (3.0, -2.0), (6.0, -2.0)]
            if self.map_mode == 'single_side':
                coordinates = [(3.0, 3.0), (6.0, 3.0)]
            if self.map_mode == 'empty':
                coordinates = []
            for identity, (x, y) in enumerate(coordinates):
                cone = ConeEstimate()
                cone.id = identity
                cone.pose.pose.position.x = 10.0 - y
                cone.pose.pose.position.y = 20.0 + x
                cone.pose.pose.orientation.w = 1.0
                cone.last_observed = message.header.stamp
                cone.detector_score = cone.depth_quality = cone.pose_quality = 1.0
                cone.association_confidence = 1.0
                cone.observation_count = cone.distinct_view_count = 2
                cone.state = ConeEstimate.PERSISTENT
                message.cones.append(cone)
            self.map_pub.publish(message)
        if self.odom_mode != 'off':
            odom = Odometry()
            odom.header.stamp = self.now()
            odom.header.frame_id = 'missing_odom' if self.odom_mode == 'missing_tf' else 'odom'
            odom.pose.pose.orientation.w = 1.0
            if self.odom_mode == 'stale':
                odom.header.stamp.sec -= 2
            self.odom_pub.publish(odom)
        if self.heartbeat_mode != 'off':
            heartbeat = RecorderHeartbeat()
            heartbeat.header.stamp = self.now()
            heartbeat.run_id = 'another-run' if self.heartbeat_mode == 'mismatch' else self.run_id
            heartbeat.state = RecorderHeartbeat.RECORDING
            heartbeat.bag_healthy = self.heartbeat_mode != 'unhealthy'
            if self.heartbeat_mode == 'stale':
                heartbeat.header.stamp.sec -= 2
            elif self.heartbeat_mode == 'future':
                heartbeat.header.stamp.sec += 2
            elif self.heartbeat_mode == 'zero':
                heartbeat.header.stamp = Time()
            self.heartbeat_pub.publish(heartbeat)

    def spin_until(self, predicate, timeout=4.0):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            self.feed()
            rclpy.spin_once(self.node, timeout_sec=0.01)
            if predicate():
                return True
        return False

    def spin_for(self, duration):
        self.spin_until(lambda: False, timeout=duration)

    def call(self, client, request):
        future = client.call_async(request)
        self.assertTrue(self.spin_until(future.done))
        self.assertIsNotNone(future.result())
        return future.result()

    def start(self, enabled=True):
        request = StartRun.Request()
        request.start = enabled
        return self.call(self.start_client, request)

    def prepare(self, name):
        self.run_id = name
        request = PrepareRun.Request()
        request.run_id_hint = name
        self.assertTrue(self.call(self.prepare_client, request).success)
        self.statuses.clear()
        self.candidates.clear()
        self.assertTrue(self.spin_until(lambda: any(c.valid for c in self.candidates)))

    def drive(self, name):
        self.map_mode = self.odom_mode = self.heartbeat_mode = 'nominal'
        self.prepare(name)
        self.assertTrue(self.spin_until(
            lambda: self.statuses and self.statuses[-1].recorder_ready))
        self.assertTrue(self.start().success)
        self.commands.clear()
        self.assertTrue(self.spin_until(lambda: len([
            c for c in self.commands if c.twist.linear.x > 0.5]) >= 4))
        self.assertTrue(any(s.run_id == name and s.state == SupervisorStatus.RACING
                            for s in self.statuses))

    def assert_stopped(self, reason):
        self.assertTrue(self.spin_until(
            lambda: self.statuses and self.statuses[-1].stop_reason == reason))
        self.commands.clear()
        self.spin_for(0.12)
        self.assertGreaterEqual(len(self.commands), 3)
        self.assertTrue(all(c.twist.linear.x == 0.0 and c.twist.angular.z == 0.0
                            for c in self.commands))
        self.assertFalse(self.start().success, 'fault latch must require new prepare')

    def test_connected_control_pipeline_and_explicit_lifecycle(self):
        self.heartbeat_mode = 'off'
        self.prepare('e2e-explicit-start')
        self.assertFalse(self.start().success, 'a recorder is required before start')
        self.heartbeat_mode = 'mismatch'
        self.spin_for(0.08)
        self.assertFalse(self.start().success)
        self.heartbeat_mode = 'nominal'
        self.assertTrue(self.spin_until(lambda: self.statuses[-1].recorder_ready))
        self.commands.clear()
        self.spin_for(0.08)
        self.assertTrue(self.commands)
        self.assertTrue(all(c.twist.linear.x == 0.0 for c in self.commands))
        self.assertTrue(self.start().success)
        self.commands.clear()
        self.assertTrue(self.spin_until(lambda: len([
            c for c in self.commands if c.twist.linear.x > 0.5]) >= 4))
        path = next(p for p in reversed(self.paths) if p.points)
        self.assertEqual(path.header.frame_id, 'map')
        self.assertAlmostEqual(path.points[0].pose.position.x, 10.0, delta=0.05)
        self.assertAlmostEqual(path.points[0].pose.position.y, 23.0, delta=0.05)
        revisions = {p.revision for p in self.paths if p.points}
        self.assertTrue(any(c.valid and c.path_revision in revisions for c in self.candidates))
        self.assertTrue(all(abs(c.twist.angular.z) < 0.05 for c in self.commands))
        owners = self.node.get_publishers_info_by_topic('/car/control_request')
        self.assertEqual([owner.node_name for owner in owners], ['e2e_supervisor'])
        self.assertTrue(self.start(enabled=False).success)
        self.assert_stopped('operator_stop')
        self.drive('e2e-reprepared')
        self.map_mode = 'single_side'
        self.paths.clear()
        self.assertTrue(self.spin_until(lambda: any(
            p.points and all(0.4 <= point.confidence < 0.75 for point in p.points)
            for p in self.paths)))
        self.assertTrue(self.commands[-1].twist.linear.x > 0.5)
        request = AbortRun.Request()
        request.reason = 'operator_abort'
        self.assertTrue(self.call(self.abort_client, request).success)
        self.assert_stopped('operator_abort')

    def test_sensor_and_path_faults_stop_the_connected_graph(self):
        scenarios = (
            ('map_mode', 'empty', 'path_empty'),
            ('map_mode', 'unsafe', 'path_unsafe'),
            ('map_mode', 'unlocalized', 'path_empty'),
            ('map_mode', 'missing_tf', 'odometry_transform_unavailable'),
            ('map_mode', 'off', 'path_stale'),
            ('odom_mode', 'missing_tf', 'odometry_transform_unavailable'),
            ('odom_mode', 'stale', 'odometry_stale'),
            ('odom_mode', 'off', 'odometry_stale'),
        )
        for index, (field, mode, reason) in enumerate(scenarios):
            with self.subTest(field=field, mode=mode):
                self.drive(f'e2e-sensor-{index}')
                setattr(self, field, mode)
                self.statuses.clear()
                self.assert_stopped(reason)

    def test_recorder_and_candidate_faults_latch_zero_output(self):
        for mode, reason in (
                ('mismatch', 'recorder_run_id_mismatch'),
                ('unhealthy', 'recorder_unhealthy'),
                ('stale', 'recorder_stale'), ('future', 'recorder_stale'),
                ('zero', 'recorder_stale'), ('off', 'recorder_stale')):
            with self.subTest(recorder=mode):
                self.drive('e2e-recorder-' + mode)
                self.heartbeat_mode = mode
                self.statuses.clear()
                self.assert_stopped(reason)
        for mode in ('stale', 'future', 'zero', 'speed', 'steering', 'nan'):
            with self.subTest(candidate=mode):
                self.drive('e2e-candidate-' + mode)
                candidate = ControlCandidate()
                candidate.header.stamp = self.now()
                candidate.header.frame_id = 'base_link'
                candidate.valid = True
                candidate.speed = 1.0
                if mode == 'stale':
                    candidate.header.stamp.sec -= 2
                elif mode == 'future':
                    candidate.header.stamp.sec += 2
                elif mode == 'zero':
                    candidate.header.stamp = Time()
                elif mode == 'speed':
                    candidate.speed = 6.0
                elif mode == 'steering':
                    candidate.steering = 0.8
                else:
                    candidate.speed = math.nan
                self.statuses.clear()
                self.fault_pub.publish(candidate)
                self.assert_stopped('candidate_stale' if mode in (
                    'stale', 'future', 'zero') else 'candidate_invalid')

    def test_marker_only_observations_cannot_authorize_motion(self):
        self.drive('e2e-marker-quarantine')
        self.map_mode = 'off'
        self.maps.clear()
        marker = Marker()
        marker.header.stamp = self.now()
        marker.header.frame_id = 'map'
        marker.id = 12
        marker.type = Marker.SPHERE
        marker.action = Marker.ADD
        marker.pose.position.x = 10.0
        marker.pose.position.y = 23.0
        marker.pose.orientation.w = 1.0
        message = MarkerArray()
        message.markers.append(marker)
        self.marker_pub.publish(message)
        self.assertTrue(self.spin_until(lambda: any(m.cones for m in self.maps)))
        adapted = next(m for m in self.maps if m.cones)
        self.assertEqual(adapted.localization_confidence, 0.0)
        self.assertEqual(adapted.cones[0].state, ConeEstimate.QUARANTINED)
        self.assert_stopped('path_empty')


@launch_testing.post_shutdown_test()
class TestRacingShutdown(unittest.TestCase):
    def test_all_production_nodes_exit_cleanly(self, proc_info):
        launch_testing.asserts.assertExitCodes(proc_info)
