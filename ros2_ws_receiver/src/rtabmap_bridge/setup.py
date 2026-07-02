from setuptools import setup, find_packages

package_name = 'rtabmap_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', ['launch/rtabmap_slam.launch.py']),
        ('share/' + package_name + '/config', ['config/ekf.yaml', 'config/quiet_cyclonedds.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='k-dev',
    maintainer_email='k-dev@todo.todo',
    description='Bridge between GStreamer/MPP and RTAB-Map for RK3588',
    license='Apache License 2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'bridge_node = rtabmap_bridge.bridge_node:main',
            'unpacker_node = rtabmap_bridge.unpacker_node:main',
            'ground_truth_broadcaster = rtabmap_bridge.ground_truth_broadcaster:main',
            'cone_landmark_processor = rtabmap_bridge.cone_landmark_processor:main',
            'cone_detector_npu = rtabmap_bridge.cone_detector_npu:main',
            'sensor_covariance_injector = rtabmap_bridge.sensor_covariance_injector:main'
        ],
    },
)
