import os
import platform
import subprocess
import rclpy
from rclpy.node import Node


def output(command):
    try:
        return subprocess.run(command, capture_output=True, text=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return 'unavailable'


class MultimediaPreflight(Node):
    def __init__(self):
        super().__init__('multimedia_preflight')
        os_release = output(['sh', '-c', '. /etc/os-release && printf "%s %s" "$NAME" "$VERSION_ID"'])
        ffmpeg = output(['ffmpeg', '-version']).splitlines()
        encoders = output(['ffmpeg', '-hide_banner', '-encoders'])
        packages = {name: output(['ros2', 'pkg', 'prefix', name]) for name in (
            'ffmpeg_image_transport', 'ffmpeg_encoder_decoder', 'zstd_image_transport')}
        message = (
            f"Orange Pi multimedia inventory (development mismatches warn): "
            f"OS={os_release} kernel={platform.release()} "
            f"ffmpeg={ffmpeg[0] if ffmpeg else 'unavailable'} "
            f"hevc_rkmpp={'available' if 'hevc_rkmpp' in encoders else 'unavailable'} "
            f"MPP={output(['ldconfig', '-p']).count('librockchip_mpp')} "
            f"RGA={output(['ldconfig', '-p']).count('librga')} "
            f"ROS_packages={packages}")
        self.get_logger().warning(message)


def main(args=None):
    rclpy.init(args=args); node = MultimediaPreflight(); rclpy.spin_once(node, timeout_sec=0.1)
    node.destroy_node(); rclpy.shutdown()
