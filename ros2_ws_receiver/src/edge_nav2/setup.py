import os
from glob import glob
from setuptools import find_packages, setup

package_name = 'edge_nav2'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='k-dev',
    maintainer_email='kennethsross20@gmail.com',
    description='Nav2 implementation for Edge Device with Ackermann bridge',
    license='Apache-2.0',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'nav2_ackermann_bridge = edge_nav2.nav2_ackermann_bridge:main'
        ],
    },
)
