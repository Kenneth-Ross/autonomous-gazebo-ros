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
        SetEnvironmentVariable(name='RMW_IMPLEMENTATION', value='rmw_cyclonedds_cpp'),
        SetEnvironmentVariable(name='CYCLONEDDS_URI', value=cyclonedds_config),
        
        # Combined Camera Encoder Node
        Node(
            package='sim_camera_encoder',
            executable='sim_camera_encoder_node',
            name='sim_camera_encoder',
            remappings=[
                ('~/super_frame', '/oakd/super_frame/image_raw'),
                ('~/super_frame/ffmpeg', '/oakd/super_frame/image_raw/ffmpeg')
            ],
            parameters=[{
                'use_sim_time': use_sim_time,
                'sim_camera_encoder.super_frame.ffmpeg.encoder': 'hevc_nvenc',
                'sim_camera_encoder.super_frame.ffmpeg.preset': 'p1',
                'sim_camera_encoder.super_frame.ffmpeg.tune': 'ull',
                'sim_camera_encoder.super_frame.ffmpeg.bit_rate': 20000000
            }],
            output='screen'
        )
    ])
