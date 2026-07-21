# Validation and Evidence

## Current result — 2026-07-20 America/Los_Angeles
- 2026-07-20 hardware trial: Orange Pi opened `hevc_rkmpp` and received RGB at approximately 30 FPS, but published no pairs because `zstd_image_transport` was absent on the simulation server. The bounded queue behaved as designed. Preflight logger formatting and a stale server DDS peer were identified and corrected; rerun pending.
- The physical link remains historically validated near 941 Mbps; current `-58` failures are treated as DDS fragmented-sample burst failures, not insufficient link bandwidth. This Jazzy build rejects CycloneDDS network channels, so unsupported pacing was reverted. The sender UDP payload ceiling was corrected from 12 MB to the Ethernet-MTU-safe 1472 B; 12 MB was an invalid interpretation of `MaxMessageSize` and could produce `EMSGSIZE` (`-58`).
- Preliminary rerun after setting `MaxMessageSize=1472B` and `FragmentSize=1344B` no longer showed the prior DDS send failure. This is diagnostic evidence only; paired 30 FPS rate, latency, bandwidth, depth integrity, and soak results remain pending.
- 2026-07-21 Orange Pi rerun confirmed both wire transports and best-effort KeepLast(2) edge subscriptions, about 123 Mbps combined bandwidth, and clean multimedia preflight. It failed acceptance because `pairs_published=0`; callback rates diverged and the reported timestamp gap grew by about five seconds per five-second interval. Absolute callback timestamps and five-second RGB/depth/pair rates are now emitted to isolate the lagging stage. The nominal script now fails on missing decoded fields or absent rate samples instead of reporting a false pass.
- Root cause: Jazzy `zstd_image_transport` 4.0.7 subscriber omits the compressed message header, so every decoded depth callback carried timestamp zero. Edge now decodes the standard Zstd payload directly, retains the exact wire header, validates bounds and decoded size, and rejects malformed payloads. Automated bit-exact/header and malformed-frame tests pass; Orange Pi rerun pending.
- First direct-decoder rerun rejected every depth frame with `Unknown frame descriptor`, proving the Jazzy publisher payload was zlib/DEFLATE rather than Zstandard. Server now publishes actual libzstd level 1 data in the documented metadata envelope; edge decodes the same envelope. Production-path deterministic, smooth, noisy, zero, maximum, exact-header, and malformed-frame tests pass on both packages; paired Orange Pi rerun pending.
- After exact pairing reached 30 FPS, starting nominal raw-topic probes reproduced edge-side `-58`. Cause was stale `<MaxMessageSize>12MB</MaxMessageSize>` in edge-generated CycloneDDS XML. Edge now matches server `1472B`/`1344B`; regression rejects the old value. No sysctl or interface queue change is required. Rerun pending.
- Correct-worktree nominal rerun retained 30.0-30.4 FPS RGB receive, depth receive, and exact pair publication in decoder counters; zero unmatched drops, zero malformed frames, bounded queue high-water 6, no DDS/FFmpeg/Zstd errors, correct image contract, and about 179.6 Mbps combined wire bandwidth. A best-effort CLI reader observed 28.75 FPS while internal publication remained 30 FPS, demonstrating allowed observer loss without sensor-path slowdown. RGB plugin publisher depth 20 remained the final QoS contract failure. Server now encodes HEVC directly with the same encoder library and publishes packets reliable KeepLast(2), retaining GOP 10 and zero B-frames; hardware rerun pending.
- Edge pairing failure traced to eager deletion of any older unmatched stamp plus reliable receive backlog. Pairer now retains unmatched stamps until bounded depth-8 capacity eviction; edge transport subscriptions request best-effort newest data; metrics report queue size and RGB-depth stamp gap. Orange Pi rerun pending.
- 2026-07-21 Orange Pi direct-RGB rerun confirmed the RGB wire publisher is reliable KeepLast(2), and the receiver sustained exact RGB-depth pairing at 30.0-30.4 FPS with zero malformed frames and a bounded queue. The 30-minute latency/resource soak and adversarial matrix remain pending.

Implementation is `[W.I.P]`. On the host, `sim_camera_encoder` built and its 6 tests passed; `sim_camera_decoder` built and its 6 tests passed; `rtabmap_bridge` built in the documented system-Python environment and its 2 launch-contract tests passed. The installed launch exposed all isolation, preview, peer, interface, and local-address arguments. No Orange Pi or end-to-end result is claimed.

Automated acceptance covers depth boundary conversion, exact timestamp matching,
missing/duplicate/out-of-order input, bounded queues, launch flag dependencies,
and DDS interface/address XML. Still required before `[VERIFICATION]`: retained
nominal and adversarial Orange Pi evidence and remaining end-to-end contract
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

## Sequenced probe scripts

Manual multi-command probes must be encoded in scripts so ordering, timeouts, environment, and evidence capture remain repeatable. Do not copy individual `ros2 topic` commands from a test case unless diagnosing a script failure.

Orange Pi camera-only nominal probe:

```bash
cd /path/to/ros2_gazebo
./scripts/validation/camera_edge_nominal.sh 30
```

The script runs preflight, required/legacy topic checks, QoS inspection, message contract samples, RGB and depth rate probes, sequential wire-bandwidth probes, and a resource snapshot. It writes one UTC-stamped log under `validation_evidence/`. Bandwidth probes are deliberately sequential because each adds a DDS reader.

Simulation-server snapshot:

```bash
cd /home/k-dev/dev/ros2_gazebo
./scripts/validation/camera_server_snapshot.sh
```

The snapshot records revision, multimedia package prefixes, installed CycloneDDS XML, network state, camera topics, and encoder process resources. Start receiver and sender before running either script.

Orange Pi 30-minute soak (with the receiver already logging to `/tmp/edge_receiver.log`):

```bash
cd /path/to/ros2_gazebo
./scripts/validation/camera_edge_soak.sh 1800 /tmp/edge_receiver.log
```

The soak fails automatically if paired rate averages below 29.5 FPS, the pairing queue exceeds 16 entries, drop/malformed counters grow, DDS/codec errors appear, p95 simulated capture-to-publication latency reaches 150 ms, thread count grows by more than two, or RSS grows above 5% after the 60-second warm-up. It emits one pasteable summary and retains a UTC-stamped evidence log.

Capture process RSS and thread counts during the soak. Latency evidence must state
clock synchronization and percentile method. If `send_packet failed` remains in
camera-only testing, record the exact error first; only `EAGAIN` justifies a
drain-and-retry wrapper patch.
