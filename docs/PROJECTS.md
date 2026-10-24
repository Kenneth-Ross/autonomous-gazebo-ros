# Active Project Audit

Statuses are `[PLAN]`, `[W.I.P]`, `[VERIFICATION]`, or `[COMPLETE]`. Source presence
is not acceptance evidence.

| Status | Project | Specification | Current progress | Next gate |
|---|---|---|---|---|
| `[VERIFICATION]` | Persistent documentation website | [Specification](../plans/DOCUMENTATION_SITE.md) | 39-page static site with search, source links, historical archive, cited SVG/Mermaid guides, and enabled auto-rebuilding user service; user-approved publication at `http://100.98.177.128:8766/` binds only localhost and this host's tailnet IP; six nominal/adversarial tests, 12 diagram grammars, staged invalid-update resilience, deterministic builds, and host-originated tailnet HTTP 200 retained in [host evidence](site/VERIFICATION.md) | Browser rendering remains unchecked because preview tooling is unavailable; cross-device reachability remains untested; starts at login, not before login |
| `[W.I.P]` | 30 FPS simulation-to-edge RGB-D streaming | [Streaming contract](STREAMING_CONTRACT.md) | Split HEVC RGB/Zstd depth implementation, depth-8 exact-stamp receiver, newest-frame transport QoS, direct HEVC/Zstd wire publishers, header-preserving Zstd decode, callback rate and in-process latency diagnostics, MTU-safe DDS generation, strict nominal, soak, edge adversarial, bit-exact depth, sender-restart, and missing-stream probes, DDS validation, and preflight | Orange Pi RKNN model loads; full-stack QoS passed; bounded SLAM feed passes; landmark 30 FPS raw-depth serialization isolated and replaced by bounded perception depth plus full-stack camera, annotations, NPU, landmarks, odometry, and RTAB-Map passed after warm-up; odometry ownership and `/rtabmap` namespace correction passed on edge; unused RGB-D odometry compute removed; 20 m cone candidate range and promotion diagnostics passed with 44 persistent landmarks and bounded candidates; C++ covariance injector passed edge verification; capture the post-change RTAB-Map performance baseline; retain pressure and decoder-comparison evidence; sender restart and missing-stream tests are optional; soak, edge faults, depth, and Ethernet rediscovery passed; corrected sender restart passed; missing-stream tests pending |
| `[W.I.P]` | Autonomous racing | [Specification](autonomous_racing_plan.md); [review fix plan](../plans/RACING_REVIEW_FIXES.md) | Canonical `autonomous_racing_msgs` package is shared by edge/server; typed recorder heartbeat and prepare/start/abort services replace prototype JSONL controls; production C++ planner, controller, and supervisor now enforce timestamped TF transforms, recorder run identity, serialized state transitions, and conservative unknown marker quality; host coverage now favors connected-control, real MCAP lifecycle/playback, and actuator E2E acceptance with four focused C++ boundary regressions; existing Gazebo lifecycle smoke retains valid MCAP artifact; server MCAP coordinator writes atomic manifests/summaries and explicit allowlists; SVG-derived Catalunya vector track is default; retained evidence in [RACING_REVIEW_FIXES_HOST.md](evidence/RACING_REVIEW_FIXES_HOST.md) | Orange Pi Gate A fixed/unseen safe-lap runs and production MCAP/Foxglove evidence; replace the marker adapter with a trusted quality-bearing cone source before movement can be authorized |
| `[W.I.P]` | Autonomous navigation acceptance | [Plan](AUTONOMOUS_TESTING_PLAN.md) | ECU/Gazebo acceptance, Jazzy behavior migration, no-spin BT, 1.35 m inflation, 11-pass edge_nav2 suite, Smac Hybrid planner pass, host closed-loop U-turn/S-turn controller pass, real Gazebo U-turn/S-turn pass, host wall-clearance costmap pass, and SVG-derived Catalunya vector map selected as server/acceptance default | Add Orange Pi deployment validation, then promote to `[VERIFICATION]` |
| `[W.I.P]` | Foxglove visualization | [Specification](FOXGLOVE_INTEGRATION.md) | Isolated by edge launch flag; preview compression is a bounded worker; host launch regression covers `/odometry/filtered` and `/racing/.*`; Desktop MCP review contract defined for local-MCAP schema, timeline, and screenshot triage | Retain one nominal and one adversarial read-only MCP review, then complete Orange Pi fault evidence; MCP remains non-gating |
| `[COMPLETE]` | Edge RTAB-Map | [Acceptance specification](../plans/RTABMAP_SLAM_ACCEPTANCE.md) | Decoder, odometry, EKF, SLAM composition, deterministic evaluator, two nominal plus one adversarial Orange Pi passes, and tested file-scoped database cleanup after container exit | None for bounded 120-second operational mapping scope; long-map scalability tracked separately |
| `[PLAN]` | RTAB-Map long-map scalability (low priority) | [Plan](../plans/RTABMAP_LONG_MAP_SCALABILITY.md) | WM 418 correlated with 575 ms delay p95 while camera and conversion stayed healthy | Profile WM 100-500, then bound graph memory without localization regression |
| `[W.I.P]` | Semantic cone perception | Current specification required | NPU and landmark nodes exist and are launch-isolated; deterministic depth, cone-geometry, projection, association, annotation, and bounded-queue helpers now have 6 host regression tests; undefined depth diagnostic no longer interrupts annotation publication | Add deterministic NPU-output tests and retained NPU evidence |
| `[W.I.P]` | Edge Nav2/control | Current specification required | Ackermann bridge, no-spin Nav2 behavior tree, moving yaw-rate cap, 11-pass host suite, and retained controller/Gazebo evidence | Orange Pi runtime and watchdog/failure evidence |

Projects enter `[VERIFICATION]` only after deterministic automated acceptance is
complete and nominal/adversarial execution can be performed. `[COMPLETE]` requires
all mandatory cases to pass with retained evidence.

## Overall status — 2026-10-12

**End-to-end autonomous driving remains `[W.I.P]`.** Local `main` now includes the
65 committed workspace/streaming changes at `e18157b2`; uncommitted documentation
work was preserved during the review. The user subsequently authorized committing
and pushing the completed source, documentation, and test consolidation. The focused
[code review](CODE_REVIEW_2026-10-12.md) found supervisor concurrency, vehicle/map
planning, map/odom control-frame, recorder identity, and perception-confidence
issues. The focused remediation is specified in
[RACING_REVIEW_FIXES.md](../plans/RACING_REVIEW_FIXES.md). The fixes now pass
nominal/adversarial host node acceptance; Gate A remains blocked on trustworthy
cone-source integration, Orange Pi deployment, and safe-lap evidence.

The initial review passed 58 selected Python regressions. Remediation now has a
fresh package build, 14 C++ regressions, two ROS-node acceptance cases, and eight
passing package CTest checks. Both new node regressions fail against original
binaries and pass after the fix. No Orange Pi execution is claimed. Existing
completed deliverables retain only their recorded bounded acceptance scope.

The documentation user service remains available at
[the tailnet site](http://100.98.177.128:8766/). Requested Tailscale Serve proxy
configuration is blocked by host privileges; HTTPS Serve also reported disabled.
An existing unrelated Serve site on port 80 is preserved. See the review for the
operator command and remaining deployment gates.

## Test consolidation

[E2E test consolidation](../plans/E2E_TEST_CONSOLIDATION.md) is `[COMPLETE]` for
its host scope: 28 duplicated/prototype unit or source-contract cases removed
after replacement acceptance passed. Connected control, real MCAP recording and
payload playback, and actuator behavior are now the recommended first check via
`racing_host_e2e.sh`. Four focused racing C++ cases and exact-boundary/transport
integrity regressions remain. Three E2E suites and all retained package checks
passed; [coverage migration and retained results](evidence/E2E_TEST_CONSOLIDATION_HOST.md)
record their boundaries. Host fixtures do not establish Orange Pi safe laps.

## End-to-end deliverable progress

| Status | Deliverable | Evidence completed | Remaining gate |
|---|---|---|---|
| `[W.I.P]` | Server simulation, vehicle, sensors, and RGB-D sender | Simulation sender implementation, direct HEVC/Zstd publishers, corrected clean sender restart, independent 300 m RGB and 30 m depth clip ranges, clean `my_gazebo_package` build/test, retained autonomous Gazebo/Nav2 evidence, and MCAP run-artifact coordinator with atomic manifest/summary lifecycle; full-launch lifecycle artifact retained | Final full-stack camera/perception performance snapshot |
| `[COMPLETE]` | Edge synchronized 1280x800 RGB-D reception at 30 FPS | Nominal probe and mandatory 30-minute soak passed at 30.280 paired FPS; bounded queue, zero drop/malformed growth, stable RSS, and 107 ms maximum window p95 | None for the camera-only acceptance scope |
| `[COMPLETE]` | Hardware HEVC decode and lossless depth reconstruction | `hevc_rkmpp` active; 30 exact-timestamp depth frames passed bit-exact comparison with zero pixel error | None for the validated codec/depth scope |
| `[COMPLETE]` | RTAB-Map SLAM map, odometry, and `map -> base_link` | Commit `28c60526` passed two nominal windows at 0.725/0.726 Hz and one pause/recovery adversarial window at 0.726 Hz; camera median held 30.2 FPS, conversion p95 stayed 2.2-2.3 ms, map TF/data and 36-41 landmarks remained active | None for bounded 120-second operational mapping scope; long-map scalability tracked separately |
| `[W.I.P]` | RKNN YOLO cone detection on the NPU | RK3588 runtime initialized and sustained detections were observed during stable 30 FPS camera operation | Add deterministic perception acceptance and retain final full-stack evidence |
| `[W.I.P]` | Depth-associated persistent cone landmarks | Exact depth association and promotion passed with 47 stable landmarks and high persistent-match counts | Add deterministic landmark regression/acceptance coverage |
| `[COMPLETE]` | C++ EKF covariance input preparation | Clean builds, exact covariance tests, linters, launch-contract tests, plugin discovery, and local runtime smoke tests passed. Orange Pi loaded the component in `vision_container`, published connected filtered odometry/IMU endpoints at 50/100 Hz, showed no standalone injector process, and logged no failures | None |
| `[W.I.P]` | Foxglove camera overlays, landmarks, SLAM, and diagnostics | Bundled image annotations with all boxes and `ID: DISTm` labels worked in the client; topic/schema collision corrected | Complete automated whitelist/launch coverage and retain fault/performance evidence |
| `[VERIFICATION]` | Camera transport resilience and integrity suite | Soak, receiver restart, slow consumer, malformed depth, bit-exact depth, sender restart, and Ethernet rediscovery passed with retained evidence | Optional missing-stream test is outside mandatory completion scope |
| `[W.I.P]` | Reproducible builds, deployment guide, validation records, and final project status | Interfaces, launch parameters, deployment, troubleshooting, host server/edge builds, autonomous acceptance, and retained camera evidence documented | Orange Pi build and final full-stack performance probe; then promote applicable projects to `[COMPLETE]` |

## Documentation website hosting — 2026-10-24

GitHub Pages is live at
`https://kenneth-ross.github.io/autonomous-gazebo-ros/`. [Run 40138371146](https://github.com/Kenneth-Ross/autonomous-gazebo-ros/actions/runs/40138371146)
passed seven documentation tests, 12 Mermaid parses, and a 39-page build. Public
HTTP checks for home, nested guide, search index, and asset returned 200. Tailnet
service remains available; browser rendering and cross-device checks remain open.
