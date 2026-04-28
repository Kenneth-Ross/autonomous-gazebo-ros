from setuptools import find_packages, setup

package_name = 'gazebo_oakd_stream_sender'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/stream_to_remote.launch.py']),
    ],
    install_requires=['setuptools', 'opencv-python', 'cv_bridge', 'PyGObject', 'numpy'],
    zip_safe=True,
    maintainer='k-dev',
    maintainer_email='kennethsross20@gmail.com',
    description='TODO: Package description',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'rgb_image_subscriber = gazebo_oakd_stream_sender.rgb_image_subscriber:main',
            'depth_image_subscriber = gazebo_oakd_stream_sender.depth_image_subscriber:main',
            'left_image_subscriber = gazebo_oakd_stream_sender.left_image_subscriber:main',
            'right_image_subscriber = gazebo_oakd_stream_sender.right_image_subscriber:main',
        ],
    },
)
