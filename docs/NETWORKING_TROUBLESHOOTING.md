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

### Fix 2: Kernel Parameter Tuning
Increased the kernel's max socket buffers to **16 MB** on both machines to prevent packet dropping during fragment reassembly.
```bash
sudo sysctl -w net.core.rmem_max=16777216
sudo sysctl -w net.core.wmem_max=16777216
```

### Fix 3: Static Peer Discovery
Configured CycloneDDS to use **Static Peers** instead of relying on multicast. This ensures that even if multicast is blocked, the Desktop and Pi have a known point of contact.
**Correct XML Structure:**
```xml
<CycloneDDS>
  <Domain id="any">
    <General>
      <Interfaces>
        <NetworkInterface name="your_interface_name"/>
      </Interfaces>
    </General>
    <Discovery>
      <Peers>
        <Peer address="10.10.12.x"/>
      </Peers>
    </Discovery>
  </Domain>
</CycloneDDS>
```

### Fix 4: Strict Parameter Typing
ROS 2 Jazzy is strict about parameter types. The launch files were updated to explicitly convert `use_sim_time` from a launch-argument string ('true') into a Python **Boolean** (True) before passing it to nodes.

---

## 4. Verification Checklist
To confirm the fix, run the following on the **Receiver (Orange Pi)**:
1. `ping 10.10.12.10` (Check physical link)
2. `ros2 topic hz /clock` (Check metadata flow)
3. `ros2 topic hz /camera/rgb/image_raw` (Check high-bandwidth flow)
