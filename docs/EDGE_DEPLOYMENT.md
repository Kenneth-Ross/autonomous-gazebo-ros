# Edge Deployment

This is the simulation-server checkout. Commands below are for the Orange Pi and are not asserted to have run.

Expected target: RK3588 Orange Pi 5-class hardware, Ubuntu 24.04, ROS 2 Jazzy, `rmw_cyclonedds_cpp`, and `edge_stack`. Decoder/NPU availability depends on actual drivers and versions.

## Orange Pi

```bash
source /opt/ros/jazzy/setup.bash
cd /path/to/ros2_gazebo/edge_stack
colcon build --symlink-install --merge-install
source install/local_setup.bash
```

Avoid Conda in ROS builds. Review setup scripts before system changes. Host and edge require compatible ROS domain, RMW, DDS discovery, and reachable interfaces. Use reviewed per-device `CYCLONEDDS_URI`; the sender has no `host:=<IP>` argument.

Collect [validation evidence](VALIDATION.md): rate, dimensions, encoding, stamps, frames, calibration, depth integrity, latency, loss/restart behavior, utilization, commit, OS/kernel, ROS/package versions, and commands.
