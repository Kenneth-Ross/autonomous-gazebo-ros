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
- The first 30-minute soak failed under its external full-resolution latency subscriber: 17.263 FPS mean pair rate, 3,566 new unmatched drops, and 195 ms p95. That observer copied every 1280×800 RGB frame through DDS and materially perturbed the edge path. Latency is now measured inside the decoder with a constant-cost five-second histogram; the soak adds no image subscriber and uses the maximum window p95 as a conservative gate. Rerun pending.
- A non-perturbing 60-second rerun passed rate, queue, drop, malformed, RSS, and thread gates but failed latency at a 173 ms maximum window p95. Window values were mostly 144-164 ms and decoder AV options were empty, indicating fixed HEVC buffering. Edge now requests `flags:low_delay` and reports RGB-decode, depth-wire, and paired-publication p95 separately; Orange Pi confirmation is pending.
- With decoder low-delay enabled, the next 60-second run improved maximum p95 to 162 ms while sustaining 30.3 FPS. Stage metrics isolated RGB decode/transport at 138-160 ms versus depth wire at 61-68 ms and only 2-3 ms pairing overhead. Installed NVENC advertises `zerolatency`, `delay`, and `rc-lookahead`; server now explicitly requests `1`, `0`, and `0` respectively. Rerun pending.
- After restarting the server with explicit NVENC zero-latency controls, the Orange Pi 60-second gate passed: 30.250 FPS mean paired output, queue maximum 1, zero drop/malformed growth, stable 145,912 KiB RSS and 23 threads, and maximum five-second-window p95 latency 100 ms. Evidence: `camera_edge_soak_20260721T191358Z.log`; the mandatory 30-minute run remains pending.
- Mandatory Orange Pi 30-minute soak passed: 30.280 FPS mean paired output across 360 windows, queue maximum 2, zero drop/malformed growth, 107 ms maximum five-second-window p95, 23 maximum threads, and RSS changed from 140,612 KiB after warm-up to 139,732 KiB (-0.626%). Evidence: `camera_edge_soak_20260721T191638Z.log`.
- First edge adversarial run passed receiver restart and malformed rejection but exposed two test defects: expected corrupt-frame warnings were classified as transport failures, and the slow probe subscribed to unbounded 30 FPS raw RGB instead of the production bounded 5 FPS preview used by NPU/Foxglove. It also confirmed `hevc_rkmpp` rejects `flags:low_delay` with `Option not found`; that default was removed. Harness now tests the production preview path and requires at least 29 FPS with no drop growth during load. Rerun pending.
- Corrected Orange Pi adversarial sequence passed receiver stop/restart recovery, bounded slow preview consumption, malformed Zstd rejection, and post-fault recovery. Slow-load pair rate stayed at least 30.2 FPS with zero drop growth; three corrupt frames produced three rejections; final recovery reached 30.4 FPS. Evidence: `camera_edge_adversarial_20260721T195926Z.log`.
- Orange Pi wire-to-edge depth integrity passed for 30 exact-timestamp frames with metadata equality and zero byte/pixel error. Evidence: `camera_depth_integrity_20260721T200517Z.log`.
- Initial sender-restart behavior recovered, but harness killed encoder child instead of owning launcher and did not prove a clean DDS zero-to-one publisher transition. Evidence is diagnostic only. Corrected harness owns launcher tree and requires zero publishers before restart plus exactly one publisher per stream after restart. User removed sender-restart recovery from mandatory completion scope; optional rerun pending.
- Second sender-restart harness proved DDS zero-to-one ownership but omitted `GZ_IP=127.0.0.1`; replacement node advertised topics then stopped receiving Gazebo frames. Its PASS is invalid. Harness now requires nonzero server RGB/depth counters and two distinct healthy edge metric windows; optional rerun pending.
- Physical dedicated-Ethernet interruption passed. Edge observed 0 FPS during disconnect, retained queue maximum 1 with no new drops, rediscovered DDS after reconnect, and recovered to 30.4 FPS with post-recovery p95 around 92-95 ms. Evidence: `camera_edge_sender_restart_20260721T201433Z.log`.

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

## Optional sender restart sequence

Start with simulation, sender, and edge receiver running. On Orange Pi:

```bash
./scripts/validation/camera_edge_sender_restart_monitor.sh /tmp/edge_receiver.log
```

After it prints `READY`, run on simulation server:

```bash
./scripts/validation/camera_server_sender_restart.sh 8
```

Server script resolves exactly one encoder PID, stops only that process, holds an eight-second outage, and starts replacement sender. Edge monitor requires baseline, observable zero-rate outage, recovery to at least 29 FPS, queue maximum 16, and no DDS/FFmpeg transport failure. Both sides retain evidence.

## Optional missing-stream sequence

After rebuilding and restarting server sender, run edge monitor:

```bash
./scripts/validation/camera_edge_missing_streams_monitor.sh /tmp/edge_receiver.log
```

After `READY`, simulation server runs:

```bash
./scripts/validation/camera_server_missing_streams.sh 10
```

Runtime gates disable RGB then depth independently. Edge must observe healthy opposite stream, zero pair output during each fault, bounded queue, no crash/transport error, and at least 29 FPS recovery after each restoration.

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

The non-perturbing soak reads decoder-internal latency windows and fails automatically if paired rate averages below 29.5 FPS, the pairing queue exceeds 16 entries, drop/malformed counters grow, DDS/codec errors appear, p95 simulated capture-to-publication latency reaches 150 ms, thread count grows by more than two, or RSS grows above 5% after the 60-second warm-up. It emits one pasteable summary and retains a UTC-stamped evidence log.

Run bit-exact depth validation while camera-only receiver is active:

```bash
cd /path/to/ros2_gazebo
./scripts/validation/camera_depth_integrity.sh 30
```

The checker subscribes to actual Zstd wire frames and edge-decoded depth, matches exact timestamps with bounded queues, decodes through system libzstd, and compares header metadata plus every `16UC1` byte. Success requires 30 matched frames and zero pixel error.

After the soak, stop the existing receiver and run the Orange Pi adversarial sequence:

```bash
cd /path/to/ros2_gazebo
./scripts/validation/camera_edge_adversarial.sh
```

This script owns and safely restarts its receiver process. It verifies baseline recovery at 29 FPS or better, receiver stop/restart, a 250 ms slow best-effort subscriber, malformed Zstd rejection, post-fault recovery, and absence of DDS/FFmpeg/Zstd transport failures. Sender restart, Ethernet interruption, missing streams, CPU/memory pressure, full-stack component restarts, and hardware/software HEVC comparison remain separate server-controlled cases.

Capture process RSS and thread counts during the soak. Latency evidence must state
clock synchronization and percentile method. If `send_packet failed` remains in
camera-only testing, record the exact error first; only `EAGAIN` justifies a
drain-and-retry wrapper patch.
- 2026-07-21 full-stack Orange Pi attempt loaded the RKNN model and initialized RK3588 NPU, Foxglove, RGB-D odometry, and RTAB-Map. It failed SLAM input because RTAB-Map requested reliable raw images while the camera contract publishes best-effort KeepLast(1). Launch now sets RTAB-Map `qos_image=2` (best-effort), retains reliable CameraInfo, and uses `sync_queue_size`; Orange Pi rerun pending.
- Follow-up runtime inspection showed `rgbd_odometry` uses parameter `qos`, not RTAB-Map CoreWrapper parameter `qos_image`; the first fix corrected CoreWrapper only. Launch now passes `qos=2` specifically to RGB-D odometry so both raw-image subscribers match best-effort camera output; Orange Pi rerun pending.
- Full-stack load then showed RGB-D odometry processing each 1280x800 pair at roughly 60-100 ms and starving camera decode to 7-17 FPS despite spatial feature/decimation tuning. Decoder now publishes a separate exact-timestamp, newest-pair SLAM feed at configurable 10 Hz while preserving 30 FPS public camera outputs; odometry and RTAB-Map remap to that feed. Orange Pi full-stack rerun pending.
- NPU-only isolation sustained 29.8-30.4 FPS paired camera output at 2 FPS perception input, proving RKNN inference was not the direct starvation source. Enabling landmarks caused the regression because its separate Python process subscribed to full 1280x800 raw depth at 30 FPS. Decoder now publishes exact-stamp raw perception depth only at bounded preview rate and landmarks consume that topic; Orange Pi rerun pending.
- After bounding landmark depth, full stack improved to 26.8-30.4 FPS with passing 96-113 ms p95 but still occasional RGB loss. Foxglove wildcard subscription kept landmark annotated preview active, causing synchronous Python JPEG decode/draw/re-encode. `publish_annotated` now defaults false; detections, landmarks, and markers remain active. Orange Pi rerun pending.
- Annotated JPEG output was replaced by `/yolo/image_annotations` using timestamp-aligned `visualization_msgs/msg/ImageMarker` line strips, supported by Foxglove Image panel. Bounding boxes are drawn client-side over the existing compressed RGB image. Landmark processor no longer subscribes to RGB, eliminating its remaining JPEG transport and synchronization overhead. Orange Pi rerun pending.
- The first client-side annotation implementation published one `visualization_msgs/msg/ImageMarker` per box; Foxglove displayed only the latest message and the schema could not carry text. It is replaced by one `foxglove_msgs/msg/ImageAnnotations` message per frame containing all `PointsAnnotation` line-loop boxes and matching `TextAnnotation` labels formatted `ID: DISTm`. Orange Pi requires `ros-jazzy-foxglove-msgs`; rerun pending.
- Orange Pi annotation probe confirmed the correct `foxglove_msgs/msg/ImageAnnotations` publisher, bridge subscription, and best-effort KeepLast(1), but received no sample. Root timestamp was unset and the two-frame exact-sync queue could evict depth before delayed RKNN detections. Root timestamp is now set, sync remains bounded at depth 8, and boxes are created before depth/geometric filters so every YOLO detection is visible; depth/ID text remains attached to valid projected detections. Rerun pending.
- Follow-up Orange Pi probe showed `/yolo/image_annotations` publisher and Foxglove subscriber with matching type/QoS but no samples, proving the landmark callback never fired. `message_filters` was replaced by an explicit exact-stamp depth map bounded to eight frames for delayed RKNN output. A separate Foxglove error exposed two schemas on `/rtabmap/landmark_detections`; landmark input moved to `/edge/landmark_detections`, leaving RTAB-Map output unambiguous. Rerun pending.
- Post-fix Orange Pi full-stack monitor passed after warm-up: paired camera output stabilized at 29.6-30.0 FPS, unmatched drops remained fixed at 11, queue stayed bounded, malformed remained zero, and paired p95 latency was 83-87 ms. RKNN detections, exact depth annotation processing, RGB-D odometry quality 310-332, and RTAB-Map 1 Hz updates remained active. An independent EKF `acceleration_gains` uninitialized warning remains for localization configuration follow-up; it did not interrupt streaming.
- Orange Pi SLAM probe found two `/odom` publishers and a landmark topic carrying two schemas. The moving `map -> base_link` transform proved RTAB-Map was active; `/rtabmap/mapData` was a false negative because CoreWrapper outputs were root-level. Launch now separates Gazebo, RGB-D, and EKF odometry, gives EKF sole odom TF ownership, namespaces CoreWrapper under `/rtabmap`, and separates landmark input from `/rtabmap/landmarks`; Orange Pi rerun pending.
- Orange Pi namespace rerun passed: one publisher each on `/odom`, `/rgbd_odometry/odom`, and `/odometry/filtered`; landmark schemas were separated; `/rtabmap/mapData` published around 0.5-0.6 Hz; and moving `map -> base_link` proved active mapping/localization. Because RGB-D odometry had zero subscribers and EKF visual fusion was intentionally disabled, the unused RGB-D odometry component and stale EKF input are now removed; rerun pending.
- Cone promotion investigation found synchronized depth and map TF healthy but no promotions; most detections were 13-20 m while new candidates were limited to 12 m. Candidate range is now configurable at a 20 m simulation default, and five-second rejection/association/promotion counters were added; Orange Pi rerun pending.
- Orange Pi 20 m cone-promotion rerun passed. Processor promoted 44 persistent cone landmarks; steady windows showed 141-254 persistent matches, zero invalid depth, zero transform rejection after startup, bounded active candidates (0-2), and only expected range/geometry rejection. Exact depth, association, promotion, and RTAB-Map landmark publication are operational.
- The Python covariance injector consumed about 73% CPU during full-stack operation. It is replaced by the `edge_sensor_filters` C++ component with exact-value odometry/IMU regression tests and five-second input-rate metrics. A clean local component and launch-integration build, plugin discovery, two covariance tests, four linters, five launch-contract tests, and runtime publication on both filtered topics passed. Orange Pi verification loaded `/sensor_covariance_injector` as component 3 in `/vision_container`; `/odom/filtered_input` and `/imu/filtered_input` each had one publisher and one subscriber; sustained rates were 50 Hz odometry and 99.8-100 Hz IMU; no standalone injector process or matching failure was present. The component-container CPU value is aggregate and is not attributed solely to this component.
- `rtabmap_edge_performance.sh` now captures a bounded post-change hardware interval and `rtabmap_performance_probe.py` reports CoreWrapper effective rate plus mean, p95, and maximum conversion, RTAB-Map, map-update, publication, and delay timing. Two parser regression tests and Python/Bash syntax checks pass. A fresh Orange Pi baseline after the C++ covariance replacement is pending before changing SLAM fidelity parameters.
- Orange Pi post-C++ baseline captured 56 RTAB-Map windows over 120 seconds: 0.471 Hz effective rate, 1515.252 ms mean and 2639.700 ms p95 conversion, 235.870 ms mean RTAB-Map processing, and 1823.107 ms mean delay. Camera pairing remained 30.0-30.4 FPS at 76-79 ms p95. CoreWrapper now consumes `/odometry/filtered` directly with an empty `odom_frame_id`, avoiding redundant timestamped odometry TF lookups during conversion while preserving EKF ownership of `odom -> base_link`; clean build and five launch-contract tests pass, Orange Pi rerun pending.
- Direct-odometry Orange Pi diagnostics showed correct remapping/QoS and stable 29.9 Hz odometry, but exact synchronization never matched the separately generated EKF and RGB-D timestamps; RTAB-Map repeatedly reported no data and did not create `map`. The input policy is now bounded approximate synchronization with a 50 ms maximum interval and queue depth 10. Upstream RGB/depth remain exact-paired by the decoder. Five launch-contract tests pass; Orange Pi rerun pending.
- Orange Pi A/B isolation with NPU enabled and landmark processing disabled captured 109 RTAB-Map windows over 120 seconds: 0.908 Hz effective rate, 1.076 ms mean/1.700 ms p95 conversion, 213.077 ms mean RTAB-Map processing, and 278.046 ms mean delay. Camera pairing remained 30 FPS. Compared with the landmark-enabled 1515.252 ms mean conversion baseline, this isolates landmark transform ingestion as the conversion bottleneck. Landmark poses remain camera-relative after a base-frame experiment produced incorrect floating heights. CoreWrapper now starts with non-blocking landmark transform lookup (`wait_for_transform=0.0`); five launch-contract tests pass and landmark-enabled Orange Pi verification is pending.
