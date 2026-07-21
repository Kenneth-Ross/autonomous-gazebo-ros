import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    config = os.path.join(
        get_package_share_directory('gazebo_oakd_stream_sender'),
        'config', 'cyclonedds.xml')
    use_sim_time = LaunchConfiguration('use_sim_time')
    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        SetEnvironmentVariable('RMW_IMPLEMENTATION', 'rmw_cyclonedds_cpp'),
        SetEnvironmentVariable('CYCLONEDDS_URI', config),
        Node(
            package='sim_camera_encoder',
            executable='sim_camera_encoder_node',
            name='sim_camera_encoder',
            remappings=[
                ('~/rgb', '/oakd/rgb/image_raw'),
                ('~/rgb/ffmpeg', '/oakd/rgb/image_raw/ffmpeg'),
                ('~/depth', '/oakd/depth/image_raw'),
                ('~/depth/zstd', '/oakd/depth/image_raw/zstd'),
            ],
            parameters=[{
                'use_sim_time': use_sim_time,
                'sim_camera_encoder.rgb.ffmpeg.encoder': 'hevc_nvenc',
                'sim_camera_encoder.rgb.ffmpeg.preset': 'p1',
                'sim_camera_encoder.rgb.ffmpeg.tune': 'ull',
                'sim_camera_encoder.rgb.ffmpeg.bit_rate': 20000000,
                'sim_camera_encoder.rgb.ffmpeg.gop_size': 10,
                'sim_camera_encoder.rgb.ffmpeg.max_b_frames': 0,
                'sim_camera_encoder.depth.zstd.compression_level': 1,
            }],
            output='screen')])
