# Autonomous Gazebo ROS 2

Simulation-to-edge stack for an autonomous Ackermann vehicle. The host runs Gazebo Harmonic; the Orange Pi workspace contains decoding, perception, localization, navigation, and telemetry.

## Status

- **Implemented:** RGB/depth capture, split HEVC RGB and lossless Zstd depth transport, exact-timestamp edge pairing, and autonomous-racing components.
- **Verified:** See [Validation](docs/VALIDATION.md). Source presence is not a passing host or edge test.
- **Test first:** [Production-flow E2E and focused boundary checks](docs/TESTING.md).
- **Current sender:** `sim_camera_encoder` produces both exact-stamped wire streams; the packed super-frame is historical.

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

The [documentation home](docs/INDEX.md) brings architecture, visual guides,
deployment, acceptance evidence, project plans, and the historical archive into
one website. Markdown is the canonical source.

```bash
python3 scripts/docs/serve_site.py --bind 127.0.0.1 --port 8766
```

Open `http://127.0.0.1:8766`. See [maintenance and persistent hosting](docs/DOCUMENTATION.md)
for dependencies, automated checks, and deployment.

Active plans define acceptance scope; deprecated plans and retrospectives are historical context. Neither source presence nor plans prove runtime behavior. No project-wide license is currently declared.
