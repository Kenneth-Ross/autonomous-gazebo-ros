from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration

def generate_launch_description():
    host_arg = DeclareLaunchArgument(
        'host',
        default_value='127.0.0.1',
        description='The target IP address for the UDP stream (e.g., Orange Pi Tailscale IP)'
    )

    host = LaunchConfiguration('host')

    return LaunchDescription([
        host_arg,
        Node(
            package='gazebo_oakd_stream_sender',
            executable='rgb_image_subscriber',
            name='rgb_streamer',
            parameters=[{'host': host}],
            output='screen'
        ),
        Node(
            package='gazebo_oakd_stream_sender',
            executable='left_image_subscriber',
            name='left_streamer',
            parameters=[{'host': host}],
            output='screen'
        ),
        Node(
            package='gazebo_oakd_stream_sender',
            executable='right_image_subscriber',
            name='right_streamer',
            parameters=[{'host': host}],
            output='screen'
        ),
    ])
