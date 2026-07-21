# Edge Deployment

This checkout is the simulation server. The following commands are Orange Pi
instructions and have not been run here.

## Orange Pi preflight and build

```bash
source /opt/ros/jazzy/setup.bash
cd /path/to/ros2_gazebo/edge_stack
colcon build --symlink-install --merge-install
source install/local_setup.bash
ros2 run rtabmap_bridge multimedia_preflight
```

The read-only preflight reports OS/kernel, FFmpeg, `hevc_rkmpp`, MPP/RGA library
visibility, and the three required ROS multimedia packages. Development mismatches
warn; promotion to `[VERIFICATION]` requires one retained known-good inventory.

Full launch, with an explicit local interface and address:

```bash
ros2 launch rtabmap_bridge rtabmap_slam.launch.py \
  network_interface:=eth0 local_address:=10.10.12.11 peer_address:=10.10.12.10
```

Camera-only isolation is the default. CycloneDDS auto-detects the local interface,
and the configured default peer is used without embedding addresses in the command:

```bash
ros2 launch rtabmap_bridge rtabmap_slam.launch.py
```

Foxglove, SLAM, NPU, landmarks, and preview compression are opt-in. Explicit
network overrides remain available when auto-detection is ambiguous.

The launch fails if the requested interface/address does not exist, or landmarks
are enabled without both NPU and SLAM. Do not keep a second active CycloneDDS file;
the generated launch XML is canonical for this pipeline.

Server sender:
The server and Orange Pi must provide `pkg-config --modversion libzstd`. The Jazzy `zstd_image_transport` plugin is inventory-only and is not used by the depth data path because version 4.0.7 drops headers and uses zlib/DEFLATE rather than Zstandard.

```bash
source /opt/ros/jazzy/setup.bash
cd /path/to/ros2_gazebo/server_sim
source install/setup.bash
ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py
```

## Orange Pi retained soak evidence

With the camera-only receiver running through `tee /tmp/edge_receiver.log`, run:

```bash
cd /path/to/ros2_gazebo
./scripts/validation/camera_edge_soak.sh 1800 /tmp/edge_receiver.log
```

This uses ROS simulated time for capture-to-edge latency and records rate, queue, error, RSS, thread, and CPU evidence. It does not require network sysctl or interface queue changes.

After the soak completes, stop the receiver launched by hand. Run the receiver-owned adversarial sequence:

```bash
./scripts/validation/camera_edge_adversarial.sh
```

Do not run this concurrently with the soak or another `/camera_decoder`.
