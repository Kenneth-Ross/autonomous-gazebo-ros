# Codex Repository Instructions

## Scope and execution boundary

- This checkout is the simulation server, not the Orange Pi edge device.
- Codex may inspect, edit, build, and test server-side files in this repository.
- Do not claim an edge-side command succeeded unless the user supplies its output or the device is explicitly available.
- Give edge-only commands under an `Orange Pi` label. Never request or collect sudo passwords.

## Architecture

- `server_sim/`: Ubuntu 24.04 / ROS 2 Jazzy simulation, Gazebo Harmonic, vehicle control, sensor encoders/senders.
- `edge_stack/`: Orange Pi receivers/decoders, SLAM, navigation, racing, telemetry, and RKNN/NPU integration.
- Data path: simulation -> encoder/sender -> network -> edge decoder/receiver -> perception/localization/control.
- Treat timestamps, frame IDs, intrinsics, depth precision, latency, and packet loss as end-to-end interface requirements.

## Working conventions

- Use spec-driven development for project work. Active project specifications must begin with exactly `[PLAN]`, `[W.I.P]`, `[VERIFICATION]`, or `[COMPLETE]`.
- Use test-driven development for implementation: add a failing specification or regression test, implement the minimum passing change, then refactor with tests green.
- `[VERIFICATION]` requires automated acceptance coverage plus retained nominal and adversarial passes; `[COMPLETE]` requires all mandatory cases to pass.
- Keep `docs/PROJECTS.md` current in the same change as project status, milestones, acceptance evidence, or deprecation.
- Start with `git status --short`; preserve unrelated user changes and generated telemetry.
- Use `rg`/`rg --files`; ignore `build/`, `install/`, and `log/` unless diagnosing artifacts.
- Edit source under workspace `src/`; never patch generated copies under `build/` or `install/`.
- Keep host and edge changes separable. Document interface, launch, topic, port, frame, parameter, dependency, and deployment changes.
- Do not commit, push, install packages, or modify the Orange Pi unless the user explicitly asks.

## Verification

- Source Jazzy when needed: `source /opt/ros/jazzy/setup.bash`.
- Host: `cd server_sim && colcon build --symlink-install`.
- Edge (Orange Pi): `cd edge_stack && colcon build --symlink-install --merge-install`.
- Prefer package-scoped checks while iterating. Separate commands actually run from hardware checks still required.
- Streaming checks cover codec/caps, rate, latency, timestamps, frame IDs, image dimensions/encoding, and depth integrity.

## Canonical workflow

Use `docs/CODEX_WORKFLOWS.md`. Treat `deprecated/gemini.md` and other files under `deprecated/` as historical context, not current instructions.
