"""Recorder RPCs -> real rosbag2 MCAP -> readable, allowlisted run artifacts."""

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
import unittest

from autonomous_racing_msgs.msg import RecorderHeartbeat
from autonomous_racing_msgs.srv import AbortRun, PrepareRun, StartRun
from geometry_msgs.msg import TwistStamped
import launch
import launch_ros.actions
import launch_testing
import launch_testing.asserts
import pytest
import rclpy
from std_msgs.msg import String
from std_srvs.srv import Trigger
import yaml


@pytest.mark.launch_test
def generate_test_description():
    artifact_root = tempfile.mkdtemp(prefix='recorder-e2e-')
    recorder = launch_ros.actions.Node(
        package='my_gazebo_package', executable='run_recorder_node.py',
        name='e2e_run_recorder', output='screen',
        parameters=[{'artifact_root': artifact_root}])
    return launch.LaunchDescription([
        recorder, launch_testing.actions.ReadyToTest()]), {
            'recorder': recorder, 'artifact_root': artifact_root}


class TestRecorderE2E(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        rclpy.init()

    @classmethod
    def tearDownClass(cls):
        rclpy.shutdown()

    def setUp(self):
        self.node = rclpy.create_node('recorder_e2e_fixture')
        self.heartbeats = []
        self.sent_stamps = set()
        self.node.create_subscription(
            RecorderHeartbeat, '/racing/recorder/heartbeat', self.heartbeats.append, 10)
        self.publisher = self.node.create_publisher(TwistStamped, '/car/control_request', 10)
        self.unrelated = self.node.create_publisher(String, '/test/not_allowlisted', 10)
        self.prepare = self.node.create_client(PrepareRun, '/racing/recorder/prepare')
        self.start = self.node.create_client(StartRun, '/racing/recorder/start')
        self.stop = self.node.create_client(Trigger, '/racing/recorder/stop')
        self.abort = self.node.create_client(AbortRun, '/racing/recorder/abort')
        for client in (self.prepare, self.start, self.stop, self.abort):
            self.assertTrue(client.wait_for_service(timeout_sec=10.0))

    def tearDown(self):
        self.node.destroy_node()

    def spin_until(self, predicate, timeout=8.0, publish=False):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if publish:
                message = TwistStamped()
                message.header.stamp = self.node.get_clock().now().to_msg()
                message.header.frame_id = 'base_link'
                message.twist.linear.x = 1.0
                self.sent_stamps.add((message.header.stamp.sec, message.header.stamp.nanosec))
                self.publisher.publish(message)
                forbidden = String()
                forbidden.data = 'must not be recorded'
                self.unrelated.publish(forbidden)
            rclpy.spin_once(self.node, timeout_sec=0.02)
            if predicate():
                return True
        return False

    def recorder_has_heartbeat_subscription(self):
        return any(endpoint.node_name != self.node.get_name() for endpoint in
                   self.node.get_subscriptions_info_by_topic('/racing/recorder/heartbeat'))

    def call(self, client, request):
        future = client.call_async(request)
        self.assertTrue(self.spin_until(future.done, timeout=15.0))
        self.assertIsNotNone(future.result())
        return future.result()

    def test_real_mcap_lifecycle_and_rejected_requests(self, artifact_root):
        root = Path(artifact_root)
        unsafe = PrepareRun.Request()
        unsafe.run_id_hint = '../escape'
        self.assertFalse(self.call(self.prepare, unsafe).success)
        self.assertEqual(list(root.iterdir()), [], 'invalid run ID created artifacts')
        for terminal in ('COMPLETE', 'ABORTED'):
            with self.subTest(terminal=terminal):
                identity = 'e2e-' + terminal.lower()
                request = PrepareRun.Request()
                request.run_id_hint = identity
                request.track_name = 'e2e-track'
                request.seed = 7
                response = self.call(self.prepare, request)
                self.assertTrue(response.success, response.message)
                self.assertEqual(response.run_id, identity)
                self.assertFalse(self.call(self.prepare, request).success,
                                 'duplicate prepare must not replace the active run')
                start = StartRun.Request()
                start.start = False
                self.assertFalse(self.call(self.start, start).success)
                start.start = True
                self.assertTrue(self.call(self.start, start).success)
                run_dir, = root.glob('run_*_' + identity)
                manifest = json.loads((run_dir / 'run_manifest.json').read_text())
                self.assertEqual(manifest['run_id'], identity)
                self.assertEqual(manifest['status'], 'PREPARED')
                self.assertEqual(manifest['track'], 'e2e-track')
                self.assertEqual(manifest['seed'], 7)
                self.assertTrue(self.spin_until(
                    lambda: self.publisher.get_subscription_count() > 0 and
                    self.recorder_has_heartbeat_subscription() and
                    any(h.run_id == identity and h.bag_healthy for h in self.heartbeats),
                    publish=True))
                self.spin_until(lambda: False, timeout=0.4, publish=True)
                if terminal == 'COMPLETE':
                    response = self.call(self.stop, Trigger.Request())
                else:
                    abort = AbortRun.Request()
                    abort.reason = 'adversarial-stop'
                    response = self.call(self.abort, abort)
                self.assertTrue(response.success, response.message)
                summary = json.loads((run_dir / 'run_summary.json').read_text())
                self.assertEqual(json.loads(response.message), summary)
                self.assertEqual(summary['run_id'], identity)
                self.assertEqual(summary['terminal_state'], terminal)
                self.assertEqual(summary['recorder_returncode'], 0)
                self.assertTrue(summary['bag_integrity']['valid'])
                heartbeat = json.loads((run_dir / 'recorder_heartbeat.json').read_text())
                self.assertEqual(heartbeat['state'], terminal)
                bag = run_dir / manifest['bag_path']
                metadata = yaml.safe_load((bag / 'metadata.yaml').read_text())[
                    'rosbag2_bagfile_information']
                counts = {entry['topic_metadata']['name']: entry['message_count']
                          for entry in metadata['topics_with_message_count']}
                self.assertGreaterEqual(counts['/car/control_request'], 3)
                self.assertGreaterEqual(counts['/racing/recorder/heartbeat'], 1)
                self.assertNotIn('/test/not_allowlisted', counts)
                self.assertTrue(set(counts).issubset(manifest['topics']))
                for segment in bag.glob('*.mcap'):
                    with segment.open('rb') as stream:
                        self.assertEqual(stream.read(8), b'\x89MCAP0\r\n')
                info = subprocess.run(
                    ['ros2', 'bag', 'info', str(bag)], capture_output=True,
                    text=True, timeout=10.0)
                self.assertEqual(info.returncode, 0, info.stderr)
                self.assertIn('/car/control_request', info.stdout)
                replayed = []
                subscription = self.node.create_subscription(
                    TwistStamped, '/test/replayed/control_request', replayed.append, 100)
                player = subprocess.Popen([
                    'ros2', 'bag', 'play', str(bag), '--topics', '/car/control_request',
                    '--remap', '/car/control_request:=/test/replayed/control_request',
                    '--delay', '0.3', '--disable-keyboard-controls',
                    '--wait-for-all-acked', '2'], stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True)
                try:
                    expected = counts['/car/control_request']
                    complete = self.spin_until(lambda: len(replayed) == expected)
                    output, _ = player.communicate(timeout=5.0)
                    self.assertEqual(player.returncode, 0, output)
                    self.assertTrue(complete, f'replayed {len(replayed)} of {expected}: {output}')
                    for recorded in replayed:
                        self.assertEqual(recorded.header.frame_id, 'base_link')
                        self.assertEqual(recorded.twist.linear.x, 1.0)
                        self.assertIn((recorded.header.stamp.sec,
                                       recorded.header.stamp.nanosec), self.sent_stamps)
                finally:
                    if player.poll() is None:
                        player.terminate()
                    player.communicate(timeout=5.0)
                    self.node.destroy_subscription(subscription)
                self.assertFalse(self.call(self.stop, Trigger.Request()).success)
                self.assertFalse(self.call(self.start, start).success)
                self.assertTrue(self.spin_until(
                    lambda: self.heartbeats and not self.heartbeats[-1].bag_healthy))
                self.assertTrue(self.spin_until(
                    lambda: self.publisher.get_subscription_count() == 0 and
                    not self.recorder_has_heartbeat_subscription()))
                print(f'RECORDER E2E {terminal}: {counts}; payload replayed; allowlist enforced')


@launch_testing.post_shutdown_test()
class TestRecorderShutdown(unittest.TestCase):
    def test_clean_exit_and_remove_test_scratch(self, proc_info, artifact_root):
        launch_testing.asserts.assertExitCodes(proc_info)
        shutil.rmtree(artifact_root)
