# Camera Pipeline Refactor (Path B)

## What Changed

The fundamental issue in the previous architecture was that **raw, uncompressed 1280x800 video frames at 30fps (215 MB/s)** were being published into the ROS 2 DDS network (via UDP) just to move data between the Gazebo bridge and the compression node on the same machine. This immediately overflowed the Linux kernel's default 212KB UDP socket buffers, causing the `ENOBUFS (-58)` errors.

### The Old Architecture (Broken)
```mermaid
graph LR
    G[Gazebo] -->|gz-transport| B[camera_bridge]
    B -->|DDS/UDP RAW 215 MB/s| S[combined_streamer]
    S -->|DDS/UDP RAW 275 MB/s| F[ffmpeg_republish]
    F -->|DDS/UDP HEVC 2.5 MB/s| E[Edge Device]
    style B fill:#f9a,stroke:#333
    style S fill:#f9a,stroke:#333
```
*Note: The nodes in red were communicating over UDP localhost, overflowing buffers.*

### The New Architecture (Fixed)
```mermaid
graph LR
    G[Gazebo] -->|gz-transport| ENode[sim_camera_encoder]
    ENode -->|DDS/UDP HEVC 2.5 MB/s| E[Edge Device]
    style ENode fill:#9f9,stroke:#333
```

I created a custom C++ node (`sim_camera_encoder`) that replaces both `camera_bridge` and `combined_streamer`. 
1. **Direct Subscription:** It subscribes directly to Gazebo (`gz::transport`) bypassing the ROS 2 bridge for raw image data.
2. **In-Process Processing:** It aligns timestamps and stacks the RGB and Depth images locally in memory.
3. **Direct Encoding:** It passes the stacked frame directly to `ffmpeg_image_transport`, which encodes it using hardware-accelerated NVENC HEVC.
4. **Network Optimized:** Only the highly compressed HEVC stream ever touches the ROS 2 DDS network.

### Files Modified/Added
- **Added:** `src/sim_camera_encoder/` (New C++ package)
- **Modified:** `launch/gazebo.launch.py` (Removed raw image bridging)
- **Modified:** `launch/stream_to_remote.launch.py` (Swapped `combined_streamer` + `republish` for the new `sim_camera_encoder` node and updated NVENC parameters)

---

## Pros

- **Eliminates `ENOBUFS` (-58):** Raw data no longer touches the network stack, permanently solving the UDP buffer overflow problem without requiring `sudo` OS tuning.
- **Hardware Accuracy:** The SIL data flow now exactly matches the real OAK-D edge flow (Lens → Local Encoder → Network), providing a more accurate simulation.
- **Resource Efficiency:** Significant reduction in CPU and memory bandwidth by eliminating 2-3 serialization/deserialization passes through DDS.
- **Lower Latency:** Fewer hops between Gazebo and the network wire decreases the "glass-to-glass" latency.

## Cons

- **Loss of Local Raw Topics:** You can no longer easily subscribe to `/sim/camera/rgb/image_raw` using `rqt_image_view` on the desktop for debugging, because those topics are no longer published to ROS 2. You must view the compressed stream or view it directly in Gazebo.
- **C++ Maintenance:** The concatenation logic is now written in C++ instead of Python, which is slightly more complex to modify if you change the OAK-D camera configuration in the future.
- **Strict Timestamping:** The new C++ node strictly requires timestamps between RGB and Depth to match within 50ms. If Gazebo lags heavily, frames may be dropped before encoding.

---

## What Should Be Tested

To verify this refactor, run the simulation (`./scripts/launch_sim.sh`) and validate the following:

1. **Stability Test:**
   - Verify that the simulation runs for >5 minutes without any `failed with retcode -58` errors in the console.
2. **Edge Reception:**
   - On the Orange Pi (`10.10.12.9`), verify that it is receiving the `/edge/camera/super_frame/ffmpeg` topic.
   - Use `ros2 topic hz /edge/camera/super_frame/ffmpeg` to confirm it is receiving frames at ~30 Hz.
3. **Image Integrity:**
   - Ensure the HEVC-decoded image on the edge device is not corrupted. The left side should be RGB, and the right side should contain the MSB and LSB depth data stacked correctly.
4. **Latency Check:**
   - Verify the glass-to-glass latency meets your 100-150ms target. (The removal of localhost DDS hops should improve this).
5. **CPU Usage:**
   - Check `htop` on the Desktop. CPU usage for the ROS 2 stack should be noticeably lower than before.
