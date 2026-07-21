#!/usr/bin/env python3
import argparse
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image


class SlowConsumer(Node):
    def __init__(self, topic, delay):
        super().__init__('adversarial_slow_consumer')
        self.delay = delay
        self.received = 0
        self.create_subscription(Image, topic, self.callback, qos_profile_sensor_data)

    def callback(self, _message):
        self.received += 1
        time.sleep(self.delay)


class CorruptDepthPublisher(Node):
    def __init__(self, topic):
        super().__init__('adversarial_corrupt_depth')
        self.publisher = self.create_publisher(CompressedImage, topic, qos_profile_sensor_data)

    def publish(self, sequence):
        message = CompressedImage()
        message.header.stamp = self.get_clock().now().to_msg()
        message.header.frame_id = 'camera_link_optical'
        message.format = '16UC1; zstd level=1 width=1280 height=800 step=2560'
        message.data = [0x00, 0x01, 0x02, sequence & 0xff]
        self.publisher.publish(message)


def run_slow(args):
    node = SlowConsumer(args.topic, args.delay)
    deadline = time.monotonic() + args.duration
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    print(f'slow_consumer_received={node.received} delay_seconds={args.delay}')
    return 0 if node.received else 1


def run_corrupt(args):
    node = CorruptDepthPublisher(args.topic)
    discovery_deadline = time.monotonic() + 5
    while rclpy.ok() and not node.publisher.get_subscription_count() and time.monotonic() < discovery_deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    if not node.publisher.get_subscription_count():
        print('ERROR: corrupt publisher found no depth subscriber')
        return 1
    for sequence in range(args.count):
        node.publish(sequence)
        rclpy.spin_once(node, timeout_sec=0.1)
        time.sleep(0.1)
    print(f'corrupt_depth_published={args.count}')
    return 0


def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest='mode', required=True)
    slow = subparsers.add_parser('slow-consumer')
    slow.add_argument('--topic', default='/edge/camera/rgb/image_raw')
    slow.add_argument('--duration', type=int, default=15)
    slow.add_argument('--delay', type=float, default=0.25)
    corrupt = subparsers.add_parser('corrupt-depth')
    corrupt.add_argument('--topic', default='/oakd/depth/image_raw/zstd')
    corrupt.add_argument('--count', type=int, default=3)
    args = parser.parse_args()
    if getattr(args, 'duration', 1) <= 0 or getattr(args, 'delay', 1) < 0 or getattr(args, 'count', 1) <= 0:
        parser.error('duration/count must be positive and delay non-negative')
    rclpy.init()
    try:
        return run_slow(args) if args.mode == 'slow-consumer' else run_corrupt(args)
    finally:
        rclpy.shutdown()


if __name__ == '__main__':
    raise SystemExit(main())
