# Networking Troubleshooting & High-Bandwidth Optimization

This document records the networking issues encountered during the integration of the Virtual OAK-D Super-Frame pipeline and the technical fixes implemented to enable reliable 1Gbps data flow between the Desktop and Orange Pi 5.

## 1. Problem: Data Starvation & Discovery Failures
**Symptoms:**
- ROS 2 nodes could "see" each other in the graph (`ros2 node list` worked), but actual data topics like `/camera/rgb/image_raw` or `/clock` showed 0 Hz on the receiver.
- SLAM nodes logged: *"Did not receive data since 5 seconds!"*
- High CPU usage on the sender, but idle CPU on the receiver.

## 2. Root Cause Analysis

### A. Subnet & Interface Mismatch
The system initially attempted to use Wi-Fi (`wlan0`). Due to unreliable multicast discovery on standard Wi-Fi routers, the nodes frequently failed to establish a direct data plane, even when discovery packets were visible.

### B. Kernel Buffer Overflows (Critical)
The default Linux kernel UDP receive buffer (`net.core.rmem_max`) is typically **212 KB**. 
- A single 1280x2400 "Super-Frame" is approximately **9 MB** raw. 
- ROS 2 (via CycloneDDS) fragments this large message into hundreds of UDP packets.
- If the kernel buffer is smaller than the burst of fragments, the OS drops the packets before the DDS layer can reassemble the frame. Loss of even one fragment destroys the entire image.

### C. CycloneDDS XML Schema Errors
Incorrect placement of the `<Peers>` element within the `CYCLONEDDS_URI` caused node crashes on startup (`unknown element`). Modern CycloneDDS requires the `<Peers>` list to be inside a `<Discovery>` block, not `<General>`.

---

## 3. Implemented Fixes

### Fix 1: Dedicated Ethernet Subnet
We migrated the high-bandwidth traffic from Wi-Fi to a dedicated **10.10.12.x** Ethernet subnet to utilize the 1Gbps physical link.
- **Desktop IP:** `10.10.12.10` (Interface: `eno1`)
- **Orange Pi IP:** `10.10.12.9` (Interface: `enP4p65s0`)

### Fix 2: Physical Link & Auto-Negotiation Diagnostics (NO-CARRIER)
During setup, the Orange Pi frequently reported a `NO-CARRIER` state on `enP4p65s0`, while the Desktop ping requests succeeded.
**Root Cause:**
1. A faulty ethernet cable prevented Auto-Negotiation from establishing a Gigabit link.
2. Due to Linux's "weak host model", the Desktop's ping requests were routing out the `eno1` interface to a local switch, broadcasting over Wi-Fi, and the Orange Pi was replying over its `wlan0` interface, falsely giving the appearance that the ethernet link was functional.

**Fix:**
1. Temporarily forced the desktop to 100Mbps to bypass the broken cable pins:
   `nmcli connection modify "Orange Pi" 802-3-ethernet.auto-negotiate no 802-3-ethernet.speed 100 802-3-ethernet.duplex full`
2. After procuring a new Cat6 cable, we reverted the interface to full Gigabit Auto-Negotiation and brought the IP profile back up to restore the 1000Mb/s link:
   `nmcli connection modify "Orange Pi" 802-3-ethernet.auto-negotiate yes 802-3-ethernet.speed 0 802-3-ethernet.duplex ""`
   `nmcli connection up "Orange Pi"`

### Fix 3: Kernel Parameter Tuning
Increased the kernel's max socket buffers to **16 MB** on both machines to prevent packet dropping during fragment reassembly.
```bash
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
```

### Fix 4: Static Peer Discovery & Network Interface Binding
Configured CycloneDDS to use **Static Peers** instead of relying on multicast. Additionally, we avoid using `<Interfaces>` blocks with `<NetworkInterface name="..."/>` which can cause parsing/binding crashes on system startups. Instead, we use `<NetworkInterfaceAddress>` to bind dynamically to a specified IP address or physical network interface (e.g., `enP4p65s0`).

**Correct XML Structure:**
```xml
<CycloneDDS xmlns="https://cdds.io/config">
  <Domain id="any">
    <General>
      <NetworkInterfaceAddress>your_interface_name_or_ip</NetworkInterfaceAddress>
      <MaxMessageSize>12MB</MaxMessageSize>
      <FragmentSize>1344B</FragmentSize>
      <AllowMulticast>spdp</AllowMulticast>
    </General>
    <Internal>
      <SocketReceiveBufferSize min="10MB"/>
    </Internal>
    <Discovery>
      <Peers>
        <Peer address="10.10.12.10"/>
      </Peers>
    </Discovery>
  </Domain>
</CycloneDDS>
```

### Fix 5: Strict Parameter Typing
ROS 2 Jazzy is strict about parameter types. The launch files were updated to explicitly convert `use_sim_time` from a launch-argument string ('true') into a Python **Boolean** (True) before passing it to nodes.

---

## 5. NPU Inference & ROS 2 Integration Issues

During edge integration on the Orange Pi 5, two major issues were encountered and fixed:

### A. RKNN Runtime OS Platform Exception
**Symptoms:**
- The `cone_detector_npu` node crashed during initialization with:
  `Exception: Unsupported run platform: Linux aarch64`
  `Failed to init_runtime with ret=-1`
**Root Cause:**
- Calling `init_runtime(target='rk3588')` on the board-native `rknn-toolkit-lite2` library triggers remote/ADB debugging helper routines. These helper routines are only supported on the full host PC `rknn-toolkit` and cause architectural detection failures on local ARM hardware.
**Fix:**
- Call `init_runtime()` with no arguments to initialize the NPU locally.

### B. Camera Info QoS Mismatch
**Symptoms:**
- The landmark processor logged:
  `New publisher discovered on topic '/camera/depth/camera_info', offering incompatible QoS. No messages will be received from it.`
**Root Cause:**
- The `unpacker_node` publishes `/camera/depth/camera_info` with a **Best Effort** QoS (`pipeline_qos`) for networking efficiency. However, the `cone_landmark_processor` subscribed to it with default **Reliable** QoS, causing the ROS 2 middleware to block the subscription.
**Fix:**
- Aligned the subscription QoS profile to `pipeline_qos` (Best Effort) inside `cone_landmark_processor.py`.

---

## 6. Network Benchtest (iperf3)
To definitively prove whether physical network bandwidth or kernel routing was causing local UDP `ENOBUFS` socket overflows, an `iperf3` test was conducted between the Host Desktop (`10.10.12.10`) and the Orange Pi (`10.10.12.9`).

**Command:** `iperf3 -c 10.10.12.9` (Run on Desktop)
**Results:**
```text
[ ID] Interval           Transfer     Bitrate         Retr
[  5]   0.00-10.00  sec  1.10 GBytes   943 Mbits/sec    0             sender
[  5]   0.00-10.00  sec  1.10 GBytes   941 Mbits/sec                  receiver
```
**Conclusion:**
The network link is a completely flawless Gigabit connection capable of pushing **110 MB/s** with **0 retries** and 0 drops. This mathematically ruled out the physical network, kernel networking stack, and ethernet auto-negotiation as the cause of local data starvation. 
The `-58` `ENOBUFS` errors were purely an architectural limitation of CycloneDDS attempting to unicast duplicate 5MB image fragments to multiple local ROS 2 ports simultaneously. To solve this, **ROS 2 Intra-Process Communication (IPC)** was implemented via a `ComposableNodeContainer` for the vision pipeline, bypassing UDP socket buffers entirely for intra-device data sharing.

---

## 7. Verification Checklist
To confirm the fix, run the following on the **Receiver (Orange Pi)**:
1. `ping 10.10.12.10` (Check physical link)
2. `ros2 topic hz /clock` (Check metadata flow)
3. `ros2 topic hz /camera/rgb/image_raw` (Check high-bandwidth flow)
4. `ros2 topic hz /yolo/detections` (Check NPU inference publishing frequency)

