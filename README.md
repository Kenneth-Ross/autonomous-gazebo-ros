# Autonomous Gazebo ROS 2

Simulation-to-edge stack for an autonomous Ackermann vehicle. The host runs Gazebo Harmonic; the Orange Pi workspace contains decoding, perception, localization, navigation, and telemetry.

## Status

- **Implemented:** RGB/depth capture, horizontal RGB-D packing, HEVC through `ffmpeg_image_transport`, edge unpacking, and autonomous-racing components.
- **Verified:** See [Validation](docs/VALIDATION.md). Source presence is not a passing host or edge test.
- **Current sender:** `sim_camera_encoder` is the sole active super-frame producer.

## Build and launch

Use ROS 2 Jazzy without an active Conda environment.

```bash
export PYTHONPATH=/usr/lib/python3/dist-packages:${PYTHONPATH:-}
./scripts/check_ros_build_env.sh
source /opt/ros/jazzy/setup.bash
cd server_sim
colcon build --symlink-install
source install/setup.bash
ros2 launch my_gazebo_package gazebo.launch.py
```

The sender accepts `use_sim_time`; it does not accept `host`:

```bash
ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py use_sim_time:=true
```

CycloneDDS configuration selects network peers/interfaces.

### Orange Pi

Run on the edge device, not this simulation host:

```bash
source /opt/ros/jazzy/setup.bash
cd edge_stack
colcon build --symlink-install --merge-install
source install/local_setup.bash
```

## Current documentation

- [Active Project Audit](docs/PROJECTS.md)
- [Current Architecture](docs/ARCHITECTURE_CURRENT.md)
- [Streaming Contract](docs/STREAMING_CONTRACT.md)
- [Edge Deployment](docs/EDGE_DEPLOYMENT.md)
- [Validation](docs/VALIDATION.md)
- [Codex Workflows](docs/CODEX_WORKFLOWS.md)

Plans and retrospectives are historical context, not proof of behavior. No project-wide license is currently declared.
