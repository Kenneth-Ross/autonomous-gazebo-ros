# Codex Workflows

These workflows replace the former Antigravity/Gemini handoff conventions.

## Audit first

1. Run `git status --short` and preserve unrelated changes.
2. Classify the change as host, edge, or wire-contract work.
3. Trace launch files, entry points, topics, parameters, ports, frames, and encodings.
4. Define host-verifiable and hardware-only checks separately.

Generated `build/` and `install/` files are not source of truth.

## Host change

```bash
source /opt/ros/jazzy/setup.bash
cd /home/k-dev/dev/ros2_gazebo/server_sim
colcon build --symlink-install --packages-select <changed_package>
source install/setup.bash
colcon test --packages-select <changed_package>
colcon test-result --verbose
```

Run the smallest relevant launch/node smoke test and record observed topics and rates.

## Streaming contract

Before changing sender or receiver, record source topics/rates, codec, pixel format, dimensions, depth representation, destination ports, timestamps, frame IDs, receiver outputs, and one-sided rollout compatibility.

Verify both ends: source publication; destination address/ports; negotiated codec/caps; restart and packet-loss behavior; reconstructed dimensions, encoding, timestamps, frame IDs and 16-bit depth; measured end-to-end rate and latency.

## Edge handoff

Codex normally runs on the server and must not report Orange Pi checks as completed without device output.

Server — completed:

- changed files and interface changes;
- commands actually run and results;
- sender command and address/port parameters.

Orange Pi — run manually:

```bash
cd <edge-checkout>
git status --short
git pull --ff-only
source /opt/ros/jazzy/setup.bash
cd edge_stack
colcon build --symlink-install --merge-install --packages-select <changed_packages>
source install/setup.bash
<receiver launch or smoke-test command>
```

Adjust paths/packages to deployment and inspect a dirty edge worktree before pulling. Useful returned diagnostics include `ros2 topic list`, `ros2 topic hz <topic>`, `ros2 topic info -v <topic>`, `ss -lunp`, node logs, and codec-specific output.

## Documentation and completion

- `plans/`: proposed or active project specifications; `docs/`: current procedures, architecture, and the authoritative `PROJECTS.md` portfolio ledger; `deprecated/`: historical approaches.
- Active project specifications use exactly `[PLAN]`, `[W.I.P]`, `[VERIFICATION]`, or `[COMPLETE]` in their H1 title.
- Update `docs/PROJECTS.md` in the same change whenever status or material progress changes.
- Documentation belongs to the same change; no missing `documenter` subagent is required.
- Report outcome, affected side, changed files, checks actually run, remaining Orange Pi checks, and deployment/rollback concerns.
- Commits and pushes are separate user-authorized actions.
