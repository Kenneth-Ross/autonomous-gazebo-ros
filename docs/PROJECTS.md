# Active Project Audit

Statuses are `[PLAN]`, `[W.I.P]`, `[VERIFICATION]`, or `[COMPLETE]`. Source presence
is not acceptance evidence.

| Status | Project | Specification | Current progress | Next gate |
|---|---|---|---|---|
| `[W.I.P]` | 30 FPS simulation-to-edge RGB-D streaming | [Streaming contract](STREAMING_CONTRACT.md) | Split HEVC RGB/Zstd depth implementation, depth-8 exact-stamp receiver, newest-frame transport QoS, direct HEVC/Zstd wire publishers, header-preserving Zstd decode, callback rate and in-process latency diagnostics, MTU-safe DDS generation, strict nominal, soak, edge adversarial, bit-exact depth, sender-restart, and missing-stream probes, DDS validation, and preflight | Orange Pi RKNN model loads; full-stack QoS passed; bounded SLAM feed passes; landmark 30 FPS raw-depth serialization isolated and replaced by bounded perception depth plus full-stack camera, annotations, NPU, landmarks, odometry, and RTAB-Map passed after warm-up; odometry ownership and `/rtabmap` namespace correction passed on edge; unused RGB-D odometry compute removed; 20 m cone candidate range and promotion diagnostics passed with 44 persistent landmarks and bounded candidates; C++ covariance injector passed edge verification; capture the post-change RTAB-Map performance baseline; retain pressure and decoder-comparison evidence; sender restart and missing-stream tests are optional; soak, edge faults, depth, and Ethernet rediscovery passed; corrected sender restart passed; missing-stream tests pending |
| `[W.I.P]` | Autonomous racing | [Plan](autonomous_racing_plan.md) | Existing controller, planner, validation, and telemetry sources | Complete behavioral and end-to-end acceptance |
| `[PLAN]` | Autonomous navigation acceptance | [Plan](AUTONOMOUS_TESTING_PLAN.md) | Procedures drafted | Execute Phase 1 with retained evidence |
| `[W.I.P]` | Foxglove visualization | [Specification](FOXGLOVE_INTEGRATION.md) | Isolated by edge launch flag; preview compression is a bounded worker | Automated launch/whitelist tests and Orange Pi fault evidence |
| `[W.I.P]` | Edge RTAB-Map | Current specification required | Decoder, odometry, EKF, and SLAM composition exist | Write current acceptance specification |
| `[W.I.P]` | Semantic cone perception | Current specification required | NPU and landmark nodes exist and are launch-isolated | Add deterministic tests and retained NPU evidence |
| `[W.I.P]` | Edge Nav2/control | Current specification required | Existing configuration and bridge | Specify and verify watchdog/failure behavior |

Projects enter `[VERIFICATION]` only after deterministic automated acceptance is
complete and nominal/adversarial execution can be performed. `[COMPLETE]` requires
all mandatory cases to pass with retained evidence.

## End-to-end deliverable progress

| Status | Deliverable | Evidence completed | Remaining gate |
|---|---|---|---|
| `[W.I.P]` | Server simulation, vehicle, sensors, and RGB-D sender | Simulation sender implementation, direct HEVC/Zstd publishers, corrected clean sender restart, and server restart evidence | Restore a clean host `colcon build`; retain final server snapshot |
| `[COMPLETE]` | Edge synchronized 1280x800 RGB-D reception at 30 FPS | Nominal probe and mandatory 30-minute soak passed at 30.280 paired FPS; bounded queue, zero drop/malformed growth, stable RSS, and 107 ms maximum window p95 | None for the camera-only acceptance scope |
| `[COMPLETE]` | Hardware HEVC decode and lossless depth reconstruction | `hevc_rkmpp` active; 30 exact-timestamp depth frames passed bit-exact comparison with zero pixel error | None for the validated codec/depth scope |
| `[W.I.P]` | RTAB-Map SLAM map, odometry, and `map -> base_link` | Moving transform and `/rtabmap/mapData` publication observed; odometry ownership and namespace corrected; repeatable RTAB-Map conversion/rate/delay performance probe added | Capture a fresh post-C++-injector baseline, reduce conversion time if still required, and retain final full-stack SLAM acceptance evidence |
| `[W.I.P]` | RKNN YOLO cone detection on the NPU | RK3588 runtime initialized and sustained detections were observed during stable 30 FPS camera operation | Add deterministic perception acceptance and retain final full-stack evidence |
| `[W.I.P]` | Depth-associated persistent cone landmarks | Exact depth association and promotion passed with 47 stable landmarks and high persistent-match counts | Add deterministic landmark regression/acceptance coverage |
| `[COMPLETE]` | C++ EKF covariance input preparation | Clean builds, exact covariance tests, linters, launch-contract tests, plugin discovery, and local runtime smoke tests passed. Orange Pi loaded the component in `vision_container`, published connected filtered odometry/IMU endpoints at 50/100 Hz, showed no standalone injector process, and logged no failures | None |
| `[W.I.P]` | Foxglove camera overlays, landmarks, SLAM, and diagnostics | Bundled image annotations with all boxes and `ID: DISTm` labels worked in the client; topic/schema collision corrected | Complete automated whitelist/launch coverage and retain fault/performance evidence |
| `[VERIFICATION]` | Camera transport resilience and integrity suite | Soak, receiver restart, slow consumer, malformed depth, bit-exact depth, sender restart, and Ethernet rediscovery passed with retained evidence | Optional missing-stream test is outside mandatory completion scope |
| `[W.I.P]` | Reproducible builds, deployment guide, validation records, and final project status | Interfaces, launch parameters, deployment, troubleshooting, and retained camera evidence documented | Clean server and Orange Pi builds; final full-stack performance probe; then promote applicable projects to `[COMPLETE]` |
