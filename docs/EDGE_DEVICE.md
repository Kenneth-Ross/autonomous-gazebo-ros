# Edge Device Specification: Orange Pi 5 (Ubuntu 24.04 / ROS 2 Jazzy)

## Hardware Profile
- **SoC:** Rockchip RK3588 (8-core: 4x A76 @ 2.4GHz, 4x A55 @ 1.8GHz)
- **NPU:** 6 TOPS (3-core)
- **RAM:** 16GB LPDDR4x
- **Storage:** **microSD Card or NVMe SSD**
- **VPU:** 8K@60fps H.265/H.264 hardware decoding (`mpphevcdec`, `mppvideodec`)

## Software Environment
- **OS:** Ubuntu 24.04 (Noble Numbat)
- **ROS 2:** Jazzy Jalisco
- **Drivers Required:** `gstreamer1.0-rockchip1` (via `ppa:jjriek/rockchip-multimedia`)

## Network Constraints
- **Primary Link:** Wi-Fi (`wlan0`) or Ethernet (`eth0`).
- **Middleware:** `rmw_cyclonedds_cpp`
- **MTU:** 1500 (Standard).
- **CycloneDDS Configuration:**
  - `FragmentSize`: 1344 (to avoid IP fragmentation).
  - `MaxMessageSize`: 10MB.
  - **Interface:** Must be manually configured in `cyclonedds.xml` or via `CYCLONEDDS_URI` env var.

## IP Identification for Deployment
On the Orange Pi, find your IP using:
```bash
ip addr show wlan0 | grep "inet "
```
Use this IP for the `host` parameter when launching the streamers on the Gazebo side.

## Critical Constraints & Mitigation
- **I/O Bottleneck:** RTAB-Map's SQLite database is configured to run in **In-Memory Mode** (`DbSqlite3/InMemory = true`) to protect the SD card and improve performance.
- **Database Persistence:** Since the map is in RAM, it must be manually exported if persistence is required.
- **Kernel Tuning:** High-bandwidth DDS requires increased kernel buffer sizes:
  ```bash
  sudo sysctl -w net.core.rmem_max=16777216
  sudo sysctl -w net.core.wmem_max=16777216
  ```

## Streaming Strategy (Bit-Split Depth)
To transmit high-fidelity 16-bit depth over standard 8-bit video channels, we use a "Bit-Split" approach:
- **Combined Frame:** [ RGB (1280x800) | MSB (1280x800) | LSB (1280x800) ]
- **Codec:** **H.265 (HEVC)** via `x265enc` (Sender) and `mpphevcdec` (Edge Device).
- **Bitrate:** 20Mbps (Minimum recommended).
- **Hardware Acceleration:** Uses Rockchip VPU for decoding and RGA for color conversion/scaling.
- **Sync:** ROS 2 Timestamps are embedded into GStreamer PTS for precise reconstruction in the `rtabmap_bridge`.
