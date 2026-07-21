# Active Project Audit

Statuses are `[PLAN]`, `[W.I.P]`, `[VERIFICATION]`, or `[COMPLETE]`. Source presence
is not acceptance evidence.

| Status | Project | Specification | Current progress | Next gate |
|---|---|---|---|---|
| `[W.I.P]` | 30 FPS simulation-to-edge RGB-D streaming | [Streaming contract](STREAMING_CONTRACT.md) | Split HEVC RGB/Zstd depth implementation, depth-8 exact-stamp receiver, newest-frame transport QoS, direct HEVC/Zstd wire publishers, header-preserving Zstd decode, callback timestamp/rate diagnostics, MTU-safe DDS generation, strict nominal and 30-minute soak probes, DDS validation, and preflight | Pass host builds/tests; then retain Orange Pi nominal, adversarial, latency, bandwidth, depth, and soak evidence |
| `[W.I.P]` | Autonomous racing | [Plan](autonomous_racing_plan.md) | Existing controller, planner, validation, and telemetry sources | Complete behavioral and end-to-end acceptance |
| `[PLAN]` | Autonomous navigation acceptance | [Plan](AUTONOMOUS_TESTING_PLAN.md) | Procedures drafted | Execute Phase 1 with retained evidence |
| `[W.I.P]` | Foxglove visualization | [Specification](FOXGLOVE_INTEGRATION.md) | Isolated by edge launch flag; preview compression is a bounded worker | Automated launch/whitelist tests and Orange Pi fault evidence |
| `[W.I.P]` | Edge RTAB-Map | Current specification required | Decoder, odometry, EKF, and SLAM composition exist | Write current acceptance specification |
| `[W.I.P]` | Semantic cone perception | Current specification required | NPU and landmark nodes exist and are launch-isolated | Add deterministic tests and retained NPU evidence |
| `[W.I.P]` | Edge Nav2/control | Current specification required | Existing configuration and bridge | Specify and verify watchdog/failure behavior |

Projects enter `[VERIFICATION]` only after deterministic automated acceptance is
complete and nominal/adversarial execution can be performed. `[COMPLETE]` requires
all mandatory cases to pass with retained evidence.
