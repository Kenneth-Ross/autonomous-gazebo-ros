#!/usr/bin/env python3
import argparse
import ctypes
import ctypes.util
import struct
import time

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, qos_profile_sensor_data
from sensor_msgs.msg import CompressedImage, Image


def stamp_ns(message):
    return message.header.stamp.sec * 1_000_000_000 + message.header.stamp.nanosec


def parse_envelope(data):
    if len(data) < 17:
        raise ValueError('short Zstd metadata')
    height, width = struct.unpack_from('<II', data, 0)
    bigendian = data[8]
    step, encoding_size = struct.unpack_from('<II', data, 9)
    metadata_size = 17 + encoding_size
    if not height or not width or not step or metadata_size >= len(data):
        raise ValueError('invalid Zstd metadata')
    encoding = bytes(data[17:metadata_size]).decode('ascii')
    return height, width, bigendian, step, encoding, metadata_size


class Zstd:
    def __init__(self):
        library = ctypes.util.find_library('zstd')
        if not library:
            raise RuntimeError('libzstd not found')
        self.library = ctypes.CDLL(library)
        self.library.ZSTD_decompress.restype = ctypes.c_size_t
        self.library.ZSTD_decompress.argtypes = [
            ctypes.c_void_p, ctypes.c_size_t, ctypes.c_void_p, ctypes.c_size_t]
        self.library.ZSTD_isError.restype = ctypes.c_uint
        self.library.ZSTD_isError.argtypes = [ctypes.c_size_t]
        self.library.ZSTD_getErrorName.restype = ctypes.c_char_p
        self.library.ZSTD_getErrorName.argtypes = [ctypes.c_size_t]

    def decompress(self, source, output_size):
        source_bytes = bytes(source)
        output = ctypes.create_string_buffer(output_size)
        source_buffer = ctypes.create_string_buffer(source_bytes)
        result = self.library.ZSTD_decompress(
            output, output_size, source_buffer, len(source_bytes))
        if self.library.ZSTD_isError(result):
            error = self.library.ZSTD_getErrorName(result).decode()
            raise ValueError(f'Zstd decode failed: {error}')
        if result != output_size:
            raise ValueError(f'Zstd size {result}, expected {output_size}')
        return output.raw


class DepthIntegrityProbe(Node):
    def __init__(self, target):
        super().__init__('depth_integrity_probe')
        self.target = target
        self.zstd = Zstd()
        self.wire = {}
        self.raw = {}
        self.compared = 0
        self.failure = None
        wire_qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST, depth=2,
            reliability=ReliabilityPolicy.BEST_EFFORT)
        self.create_subscription(
            CompressedImage, '/oakd/depth/image_raw/zstd', self.on_wire, wire_qos)
        self.create_subscription(
            Image, '/edge/camera/depth/image_raw', self.on_raw, qos_profile_sensor_data)

    def on_wire(self, message):
        try:
            metadata = parse_envelope(message.data)
            height, width, bigendian, step, encoding, start = metadata
            decoded = self.zstd.decompress(message.data[start:], height * step)
            self.wire[stamp_ns(message)] = (
                message.header.frame_id, height, width, bigendian, step, encoding, decoded)
            self.trim(self.wire)
            self.compare(stamp_ns(message))
        except (ValueError, UnicodeDecodeError) as error:
            self.failure = str(error)

    def on_raw(self, message):
        self.raw[stamp_ns(message)] = (
            message.header.frame_id, message.height, message.width, message.is_bigendian,
            message.step, message.encoding, bytes(message.data))
        self.trim(self.raw)
        self.compare(stamp_ns(message))

    @staticmethod
    def trim(queue):
        while len(queue) > 4:
            del queue[min(queue)]

    def compare(self, stamp):
        if stamp not in self.wire or stamp not in self.raw:
            return
        wire = self.wire.pop(stamp)
        raw = self.raw.pop(stamp)
        if wire != raw:
            labels = ('frame_id', 'height', 'width', 'is_bigendian', 'step', 'encoding', 'data')
            field = next(label for label, left, right in zip(labels, wire, raw) if left != right)
            self.failure = f'mismatch stamp={stamp} field={field}'
            return
        self.compared += 1


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('samples', nargs='?', type=int, default=30)
    parser.add_argument('--timeout', type=int, default=30)
    args = parser.parse_args()
    if args.samples <= 0 or args.timeout <= 0:
        parser.error('samples and timeout must be positive')
    rclpy.init()
    node = DepthIntegrityProbe(args.samples)
    deadline = time.monotonic() + args.timeout
    while rclpy.ok() and node.compared < args.samples and not node.failure and time.monotonic() < deadline:
        rclpy.spin_once(node, timeout_sec=0.1)
    compared, failure = node.compared, node.failure
    node.destroy_node()
    rclpy.shutdown()
    if failure:
        print(f'ERROR: {failure} compared={compared}')
        return 1
    if compared < args.samples:
        print(f'ERROR: timeout compared={compared} target={args.samples}')
        return 1
    print(f'PASS: bit_exact_depth_frames={compared} pixel_error=0')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
