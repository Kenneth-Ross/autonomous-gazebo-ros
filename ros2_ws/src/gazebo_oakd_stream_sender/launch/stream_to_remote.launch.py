import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import SetEnvironmentVariable, DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    pkg_share = get_package_share_directory('gazebo_oakd_stream_sender')
    cyclonedds_config = os.path.join(pkg_share, 'config', 'cyclonedds.xml')

    use_sim_time = LaunchConfiguration('use_sim_time', default='true')

    return LaunchDescription([
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_config),
        SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value='rmw_cyclonedds_cpp'),
        
        # 1. The Virtual OAK-D Super-Frame Streamer
        # This node stacks RGB and Depth (MSB/LSB) into a 1280x2400 frame
        Node(
            package='gazebo_oakd_stream_sender',
            executable='combined_streamer',
            name='oakd_combined_streamer',
            parameters=[{'use_sim_time': use_sim_time}],
            output='screen'
        ),
        
        # 2. FFmpeg Image Transport Republish (Encoder)
        # Encodes the Super-Frame using hardware-accelerated HEVC
        Node(
            package='image_transport',
            executable='republish',
            name='ffmpeg_republish',
            arguments=['raw', 'ffmpeg'],
            remappings=[
                ('in', '/oakd_combined_streamer/super_frame_local'),
                ('out/ffmpeg', '/oakd/super_frame/image_raw/ffmpeg')
            ],
            parameters=[{
                'ffmpeg.encoder': 'hevc_nvenc', # Default to NVIDIA NVENC
                'ffmpeg.preset': 'p1',         # Lowest latency for NVENC
                'ffmpeg.tune': 'ull',          # Ultra-low latency
                'ffmpeg.bit_rate': 20000000    # 20 Mbps for high fidelity
            }],
            output='screen'
        ),
    ])
