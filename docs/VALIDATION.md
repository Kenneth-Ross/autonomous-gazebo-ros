# Validation and Evidence

## Current result — 2026-07-20 America/Los_Angeles

Implementation is `[W.I.P]`. On the host, `sim_camera_encoder` built and its 6 tests passed; `sim_camera_decoder` built and its 5 tests passed; `rtabmap_bridge` built in the documented system-Python environment and its 2 launch-contract tests passed. The installed launch exposed all isolation, preview, peer, interface, and local-address arguments. No Orange Pi or end-to-end result is claimed.

Automated acceptance covers depth boundary conversion, exact timestamp matching,
missing/duplicate/out-of-order input, bounded queues, launch flag dependencies,
and DDS interface/address XML. Still required before `[VERIFICATION]`: retained
nominal and adversarial Orange Pi evidence and automated Zstd round-trip/contract
coverage that runs in the deployment environment.

## Required nominal evidence

- Camera-only and full-stack RGB/depth raw output at 30 FPS.
- p95 capture-to-edge publication latency below 150 ms with synchronized clocks.
- Combined wire bandwidth below 200 Mbps and bit-exact depth pixels.
- No FFmpeg packet or DDS send failures.
- 30-minute soak without sustained rate gaps, thread/queue growth, or RSS growth
  above 5% after warm-up.
- OS/kernel, FFmpeg build, MPP/RGA, `hevc_rkmpp`, ROS multimedia package inventory.

## Required adversarial evidence

Independently restart sender, receiver, Foxglove, SLAM, and NPU; interrupt Ethernet
and rediscover DDS; slow NPU/Foxglove; remove either stream; corrupt Zstd input;
delay/reorder pairs; apply CPU/memory pressure; and compare hardware `hevc_rkmpp`
with software `hevc` on identical recorded packets. Retain commands, revision,
timestamps, expected/observed behavior, metrics, logs, artifacts, and verdict.

## Measurement commands

```bash
ros2 topic hz /edge/camera/rgb/image_raw
ros2 topic hz /edge/camera/depth/image_raw
ros2 topic info -v /oakd/rgb/image_raw/ffmpeg
ros2 topic info -v /oakd/depth/image_raw/zstd
ros2 topic bw /oakd/rgb/image_raw/ffmpeg
ros2 topic bw /oakd/depth/image_raw/zstd
```

Capture process RSS and thread counts during the soak. Latency evidence must state
clock synchronization and percentile method. If `send_packet failed` remains in
camera-only testing, record the exact error first; only `EAGAIN` justifies a
drain-and-retry wrapper patch.
