# [W.I.P] Simulation-to-Edge RGB-D Streaming Contract

**Status: implemented, not recorded as end-to-end verified.**

| Field | Current value |
|---|---|
| Layout | Horizontal `RGB | depth MSB | depth LSB` |
| Plane / packed size | 1280×800 / 3840×800 |
| Packed encoding | `bgr8` |
| Depth | Float metres to `16UC1` millimetres |
| Byte planes | MSB/LSB, each replicated across BGR |
| Timestamp / frame | RGB Gazebo stamp / `camera_link_optical` |
| Pair tolerance | 50 ms |

The decoder reconstructs `(MSB << 8) | LSB`. Invalid/out-of-range depth semantics are unspecified.

## Transport

- Base topic: `/oakd/super_frame/image_raw`
- `ffmpeg_image_transport` through ROS 2/DDS
- Current encoder/bitrate: `hevc_nvenc`, 20,000,000 bit/s
- Outputs: `/edge/camera/rgb/image_raw` (`bgr8`) and `/edge/camera/depth/image_raw` (`16UC1`)
- Camera info: `/edge/camera/{rgb,depth}/camera_info`

This is not direct UDP/RTSP and has no `host` launch argument. CycloneDDS controls discovery/interfaces. HEVC is lossy; replicated bytes do not prove bit-exact depth. Test the real path.

`sim_camera_encoder` is the sole producer in the active sender launch.
