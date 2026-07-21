#!/usr/bin/env python3
import argparse
import math
import statistics
import time

import rclpy
from rclpy.parameter import Parameter
from rclpy.node import Node
from rclpy.qos import qos_profile_sensor_data
from sensor_msgs.msg import Image


class LatencyProbe(Node):
    def __init__(self, topic):
        super().__init__(
            'image_latency_probe',
            parameter_overrides=[Parameter('use_sim_time', value=True)])
        self.samples = []
        self.create_subscription(Image, topic, self.callback, qos_profile_sensor_data)

    def callback(self, message):
        stamp_ns = message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec
        now_ns = self.get_clock().now().nanoseconds
        if stamp_ns > 0 and now_ns >= stamp_ns:
            self.samples.append((now_ns - stamp_ns) / 1_000_000.0)


def percentile(values, fraction):
    if not values:
        raise ValueError('percentile requires at least one value')
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('duration', type=int)
    parser.add_argument('--topic', default='/edge/camera/rgb/image_raw')
    args = parser.parse_args()
    if args.duration <= 0:
        parser.error('duration must be positive')
    rclpy.init()
    node = LatencyProbe(args.topic)
    deadline = time.monotonic() + args.duration
    while rclpy.ok() and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    samples = node.samples
    node.destroy_node()
    rclpy.shutdown()
    if not samples:
        print('ERROR: no latency samples')
        return 1
    print(
        f'samples={len(samples)} mean_ms={statistics.fmean(samples):.3f} '
        f'p95_ms={percentile(samples, 0.95):.3f} max_ms={max(samples):.3f}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
