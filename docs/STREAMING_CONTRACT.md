# [W.I.P] 30 FPS RGB + Lossless Zstd Depth Pipeline

The active wire contract is two exact-timestamp image transports. The legacy packed
`RGB | depth MSB | depth LSB` super-frame and `/oakd/super_frame/image_raw/ffmpeg`
topic are not part of this contract.

| Stream | Wire topic | Source/output encoding | Size | Transport |
|---|---|---|---|---|
| RGB | `/oakd/rgb/image_raw/ffmpeg` | `bgr8` | 1280×800 | HEVC/NVENC, 20 Mbps initial target |
| Depth | `/oakd/depth/image_raw/zstd` | `16UC1` millimetres | 1280×800 | lossless Zstd level 1 |

Both messages in a pair carry the identical Gazebo timestamp and
`camera_link_optical`. Float depth metres convert once on the server: non-finite,
negative, and zero values become `0`; finite values round to the nearest millimetre;
values at or above 65.535 m saturate to `65535`.

Wire publishers use direct reliable KeepLast(2) publishers. RGB packets are produced with `ffmpeg_encoder_decoder` directly because `ffmpeg_image_transport` forces publisher depth to at least twice GOP size (20 for GOP 10), violating the shallow wire queue contract. Edge transport subscriptions request best-effort KeepLast(2) from those compatible publishers, preventing stale reliable backlog when codec rates differ. ROS 2 Jazzy `zstd_image_transport` 4.0.7 omits `CompressedImage.header` and its implementation uses zlib/DEFLATE rather than Zstandard. The server and edge therefore use a small standard `CompressedImage` metadata envelope with actual libzstd level 1 compression. The edge decoder reads this payload directly with libzstd, validates metadata and decoded size, and copies the wire header exactly; malformed payloads increment the malformed counter and are dropped. Receiver callbacks only enqueue shared messages. A worker matches exact timestamps in a configurable bounded window (`pairing_queue_depth`, default 8), evicts only on capacity, drops old incomplete data, and publishes the newest complete pair. Edge raw
outputs use sensor-data best-effort KeepLast(1); CameraInfo uses reliable KeepLast(1):

- `/edge/camera/rgb/image_raw` (`bgr8`)
- `/edge/camera/depth/image_raw` (`16UC1`)
- `/edge/camera/{rgb,depth}/camera_info`

JPEG/PNG preview compression uses a separate one-slot worker at
`preview_rate_hz:=5.0` by default. It is observability output and cannot apply
backpressure to raw camera publication.
Camera-only operation is the launch default; preview, Foxglove, SLAM, NPU, and landmarks are opt-in.

Landmark processing consumes `/edge/perception/depth/image_raw`, published by the bounded preview worker with the same timestamp and rate as YOLO RGB input. It must not subscribe to the 30 FPS full-resolution public depth topic from its separate Python process.
Landmark processing publishes one bundled `foxglove_msgs/msg/ImageAnnotations` message per perception frame on `/yolo/image_annotations`. It contains every bounding box as a `PointsAnnotation` `LINE_LOOP` plus a `TextAnnotation` formatted `ID: DISTm` (for example, `1: 3.0m`), all using the source image timestamp and pixel coordinates. Foxglove overlays these on `/edge/camera/rgb/image_raw/compressed`; no annotated JPEG is generated. Landmark processing does not subscribe to RGB.
Delayed detections are matched to perception depth by an explicit exact-timestamp map bounded to eight frames. Landmark input to RTAB-Map uses `/edge/landmark_detections`; RTAB-Map's PoseArray output remains `/rtabmap/landmarks`, so each topic has one schema.
The landmark processor performs camera-to-map association and one camera-to-`base_link` transform per detection frame. RTAB-Map landmark messages are published in `base_link`, preventing CoreWrapper from repeating the same camera-frame transform for every persistent detection.



Full-stack SLAM consumes an internal exact-pair feed on `/edge/slam/{rgb,depth}/{image_raw,camera_info}`. The decoder gates this newest synchronized feed to configurable `slam_rate_hz` (default 10 Hz), while public `/edge/camera/...` sensor outputs remain 30 FPS. Both image feeds use best-effort KeepLast(1); CameraInfo remains reliable KeepLast(1).
Full-stack odometry ownership is explicit: Gazebo publishes `/odom`, the covariance injector feeds the EKF, the EKF owns `odom -> base_link`, and namespaced RTAB-Map consumes `/odometry/filtered` directly while publishing maps under `/rtabmap/*`; its empty `odom_frame_id` avoids redundant timestamped odometry TF lookups. RTAB-Map uses bounded approximate synchronization (50 ms interval, queue 10) to associate the 30 Hz EKF stream with the upstream exact-paired 10 Hz RGB-D feed. RGB-D odometry is not launched because visual-odometry fusion is disabled.
Sensor covariance injection is a C++ component in `vision_container`. It preserves legacy odometry and IMU covariance values, uses sensor-data QoS, and reports five-second input rates without a separate Python process.
Landmark candidate creation range is configurable with `landmark_candidate_max_range_m` (simulation default 20 m); hard processing cutoff is `landmark_max_range_m` (default 20 m). Five-second `Landmark promotion` metrics report depth, range, geometry, transform, association, creation, and promotion outcomes.

Edge exposes optional `rgb_decoder_av_options`, default empty. Orange Pi `hevc_rkmpp` rejected `flags:low_delay`, so it is not requested. Stage p95 metrics distinguish RGB decode, depth wire arrival, and final paired publication.

NVENC launch policy requests `hevc_nvenc`, preset `p1`, ultra-low-latency tuning,
GOP 10, zero B-frames, 20 Mbps, `zerolatency=1`, `delay=0`, and `rc-lookahead=0`. Confirm actual supported options and negotiated
caps in Orange Pi evidence; unsupported wrapper options must not be described as
confirmed behavior.

Decoder metrics calculate capture-to-publication latency in-process using simulated time and a fixed histogram; validation gates the maximum five-second-window p95 without adding a raw-image DDS subscriber.

Acceptance remains pending: both edge raw topics at 30 FPS, p95 end-to-end latency
below 150 ms, combined encoded bandwidth below 200 Mbps, zero depth pixel error,
no FFmpeg/DDS send failures, and a stable 30-minute run.
