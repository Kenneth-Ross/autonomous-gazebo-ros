from setuptools import find_packages, setup
import os
from glob import glob

package_name = 'rtabmap_bridge'
setup(name=package_name, version='0.1.0', packages=find_packages(exclude=['test']),
    data_files=[('share/ament_index/resource_index/packages', ['resource/' + package_name]),
      ('share/' + package_name, ['package.xml']),
      (os.path.join('share', package_name, 'launch'), glob('launch/*.launch.py')),
      (os.path.join('share', package_name, 'config'), glob('config/*'))],
    install_requires=['setuptools'], zip_safe=True, maintainer='k-dev',
    maintainer_email='kennethsross20@gmail.com', description='Edge RGB-D and RTAB-Map bridge',
    license='MIT', tests_require=['pytest'], entry_points={'console_scripts': [
      'cone_detector_npu = rtabmap_bridge.cone_detector_npu:main',
      'cone_landmark_processor = rtabmap_bridge.cone_landmark_processor:main',
      'ground_truth_broadcaster = rtabmap_bridge.ground_truth_broadcaster:main',
      'sensor_covariance_injector = rtabmap_bridge.sensor_covariance_injector:main',
      'multimedia_preflight = rtabmap_bridge.multimedia_preflight:main']})
