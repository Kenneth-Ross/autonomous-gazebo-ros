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

Camera-only isolation:

```bash
ros2 launch rtabmap_bridge rtabmap_slam.launch.py \
  enable_foxglove:=false enable_slam:=false enable_npu:=false \
  enable_landmarks:=false enable_preview_compression:=false \
  network_interface:=eth0 local_address:=10.10.12.11 peer_address:=10.10.12.10
```

The launch fails if the requested interface/address does not exist, or landmarks
are enabled without both NPU and SLAM. Do not keep a second active CycloneDDS file;
the generated launch XML is canonical for this pipeline.

Server sender:

```bash
source /opt/ros/jazzy/setup.bash
cd /path/to/ros2_gazebo/server_sim
source install/setup.bash
ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py
```
