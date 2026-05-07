# Streaming Strategy: Synchronized Bit-Split H.264/H.265

To avoid "Library Hell" on the Orange Pi 5 (where ROS 2 Foxy's OpenCV 4.2.0 conflicts with Rockchip's OpenCV 4.5.4), this project uses a custom NumPy-based reconstruction path that bypasses `cv_bridge` and `libopencv` entirely for the high-throughput data path.

## 1. Encoding (Sender Side - Gazebo)
We combine RGB and 16-bit Depth into a single 3840x800 frame:
- **Frame Layout:** `[ RGB (1280px) | Depth MSB (1280px) | Depth LSB (1280px) ]`
- **Bit-Splitting:** The 16-bit depth is split into Most Significant Byte (MSB) and Least Significant Byte (LSB).
- **Transport:** The combined frame is encoded as H.264 or H.265. By replicating MSB and LSB across all three BGR channels, we ensure the data is preserved in the **Luminance (Y)** channel of the 4:2:0 video stream, protecting it from chroma subsampling artifacts.

## 2. Decoding & Reconstruction (Receiver Side - Orange Pi)
1. **Hardware Decoding:** The Orange Pi uses the `mppvideodec` (VPU) to decode the H.265 stream with 0% CPU impact.
2. **NumPy Slicing:** The raw BGR buffer is mapped directly to a NumPy array.
3. **Reconstruction:**
   ```python
   # Reconstruct 16-bit millimeters from the MSB and LSB slices
   depth_16bit = (msb.astype(np.uint16) << 8) | lsb.astype(np.uint16)
   ```
4. **Direct ROS 2 Publishing:** The `sensor_msgs/Image` message is populated manually using the `.tobytes()` method of the NumPy array. This avoids the need for `cv_bridge` and its associated OpenCV dependency conflicts.

## 3. Advantages
- **Atomic Sync:** RGB and Depth are part of the same video frame; they can never be desynchronized by network jitter.
- **Library Independence:** No dependency on OpenCV shared libraries on the edge device for the SLAM data path.
- **Performance:** Leverages RK3588 VPU for decoding and NumPy's vectorized operations for reconstruction.
