# Orange Pi Edge Target

This is a hardware-capabilities reference for the intended edge target. Use [EDGE_DEPLOYMENT.md](EDGE_DEPLOYMENT.md) for commands and [VALIDATION.md](VALIDATION.md) for measured results.

## Target profile

- Orange Pi 5-class board with Rockchip RK3588
- 4× Cortex-A76 and 4× Cortex-A55 CPU cores
- RKNN-capable NPU, commonly advertised at up to 6 TOPS
- Rockchip VPU with H.264/H.265 decode capability
- Project target: Ubuntu 24.04 and ROS 2 Jazzy
- Project middleware: `rmw_cyclonedds_cpp`

RAM, storage, clocks, kernel, multimedia packages, plugin names, and achievable throughput depend on the specific board image. Confirm them on the deployed device rather than inferring them from this target profile.

## Required device inventory

Capture this information during deployment:

```bash
uname -a
cat /etc/os-release
lscpu
free -h
lsblk
ip -br link
ip -br address
ros2 doctor --report
```

Inventory the installed FFmpeg/GStreamer/Rockchip components using the package and plugin tools provided by the deployed image. Do not assume names such as `mpphevcdec`, `mppvideodec`, or `hevc_rkmpp` are interchangeable or installed.

## Network expectations

- Prefer dedicated Ethernet for sustained camera traffic.
- Do not hardcode interface names such as `eth0` or `wlan0`; discover them with `ip -br address`.
- The active sender has no `host:=<IP>` parameter. ROS 2 discovery and routing are controlled through CycloneDDS configuration.
- The checked-in configuration uses a standard MTU and DDS fragmentation/buffer settings; validate these against the deployed CycloneDDS version.
- Apply kernel buffer changes only after measuring drops and recording the prior values. See [NETWORKING_TROUBLESHOOTING.md](NETWORKING_TROUBLESHOOTING.md).

## Camera workload

The active contract is defined in [STREAMING_CONTRACT.md](STREAMING_CONTRACT.md):

- horizontal `RGB | depth MSB | depth LSB` packing;
- 1280×800 planes and a 3840×800 packed image;
- HEVC through `ffmpeg_image_transport` over ROS 2/DDS;
- reconstructed `bgr8` RGB and `16UC1` millimetre depth.

The host currently requests `hevc_nvenc` at 20 Mbit/s. Edge decoding acceleration depends on the FFmpeg/image-transport build installed on the Orange Pi and must be verified from runtime logs and utilization.

## Storage and persistence

RTAB-Map is currently configured with an in-memory SQLite database. This reduces storage writes but does not preserve the map across process/device restarts. Add and test an explicit export/persistence procedure before relying on generated maps operationally.
