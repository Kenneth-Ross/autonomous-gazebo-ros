# Edge Device Specification: Orange Pi 5 Pro

## Hardware Profile
- **SoC:** Rockchip RK3588S (8-core: 4x A76 @ 2.4GHz, 4x A55 @ 1.8GHz)
- **NPU:** 6 TOPS (3-core)
- **RAM:** 16GB LPDDR4x
- **Storage:** **microSD Card (No SSD)**
- **VPU:** 8K@60fps H.265/H.264 hardware decoding (`mppvideodec`)

## Software Environment
- **OS:** Orange Pi Official Ubuntu 20.04 Focal Fossa
- **ROS 2:** Foxy Fitzroy
- **Drivers Required:** `gstreamer1.0-rockchip` (for `mppvideodec`)

## Network Constraints
- **Primary Link:** **Physical Ethernet (Mandatory)**. 
- **Interface:** `eth0`
- **Bandwidth:** 1Gbps recommended.
- **Latency:** Target <2ms (local network).
- **MTU:** 1500 (Standard) - Requires `Cyclone DDS` to handle large 16-bit depth packets.

## IP Identification for Deployment
On the Orange Pi, find your Ethernet IP using:
```bash
ip addr show eth0 | grep "inet "
```
Use this IP for the `host` parameter when launching the streamers on the Gazebo side.

## Critical Constraints & Mitigation
- **I/O Bottleneck:** SD cards have low IOPS and high latency. RTAB-Map's SQLite database will be configured to run in **In-Memory Mode** (`DbSqlite3/InMemory = true`).
- **Database Persistence:** Since the map is in RAM, it must be manually exported to the SD card at the end of a session if persistence is required.
- **Swap:** Avoid swap usage on the SD card to prevent wear and system stuttering.

## Streaming Strategy
- **RGB:** UDP Port 5000 (H.264, Hardware Decoded)
- **Depth:** UDP Port 5001 (PNG 16-bit, CPU Decoded)
- **Sync:** ApproximateTime Synchronization using Gazebo timestamps.
