import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'autonomous_racing'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'launch'), glob(os.path.join('launch', '*launch.[pxy][yma]*'))),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='k-dev',
    maintainer_email='kennethsross20@gmail.com',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'pure_pursuit_node = autonomous_racing.pure_pursuit_node:main',
            'race_validator_node = autonomous_racing.race_validator_node:main',
            'telemetry_recorder_node = autonomous_racing.telemetry_recorder_node:main',
            'reactive_midline_node = autonomous_racing.reactive_midline_node:main',
            'test_orchestrator_node = autonomous_racing.test_orchestrator_node:main',
        ],
    },
)
