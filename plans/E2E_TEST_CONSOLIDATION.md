# [COMPLETE] E2E test consolidation

## Goal and scope

Favor observable production behavior over unit-count growth and source-text
assertions. Consolidate host racing, recorder, and actuator coverage without
changing production nodes, topics, messages, or Orange Pi deployment. Preserve
codec/depth, perception geometry, destructive-file-boundary, and exact-time
regressions that higher-level runs cannot exercise reliably.

## Migration

- Replace the disconnected racing launch harness with a connected production
  ConeMap -> planner -> controller -> supervisor -> control request graph.
  Fixtures supply only trusted cone observations, odometry/TF, and recorder
  heartbeat; fault injection may publish a bad candidate. No nominal path or
  candidate is manufactured by the test.
- Cover nominal/one-sided geometry, explicit preparation/start, no-recorder
  interlock, abort/reprepare, empty/unsafe/stale paths, missing map/odom TF,
  stale odometry, mismatched/unhealthy/missing/stale/future/zero recorder stamps,
  and visualization-marker quarantine through the graph.
- Exercise the production recorder service with real rosbag2 MCAP output:
  invalid run ID, duplicate active prepare, recorded allowlisted messages,
  stop/abort, summary/manifest identity, readable bag metadata, and no unrelated
  topic. Retain strict configuration validation as a focused unit test.
- Remove obsolete Python prototype gate tests, source-string racing/interface
  tests, redundant core tests, fake-recorder file tests, and actuator slew units
  covered by the existing live node acceptance. Keep camera/vehicle configuration
  tests until full Gazebo acceptance covers their exact requirements.

## Acceptance and execution order

1. Add a connected-graph regression first and retain its failure against the
   existing disconnected harness.
2. Connect the harness; run nominal and adversarial ROS acceptance successfully
   before removing the unit cases it supersedes.
3. Add and run real recorder lifecycle acceptance before removing fake recorder
   and duplicate file-shape cases.
4. Package-scoped source builds, remaining focused tests, lints, and documentation
   build must pass. Retain failure and passing evidence with migration counts.
5. No Orange Pi or full vehicle/sensor E2E result is inferred from host fixtures.
   Existing Gazebo and camera-to-edge acceptance runners remain separate gates.

## Status

Host consolidation is complete: 28 redundant cases removed only after the
connected control and real-recorder replacements passed. Registered E2E runner,
remaining package units/lints, affected builds, and syntax checks pass. Retained
nominal/adversarial and initial failing connected-flow output are in
[host evidence](../docs/evidence/E2E_TEST_CONSOLIDATION_HOST.md).

The [testing guide](../docs/TESTING.md) makes E2E the recommended first check and
records retained boundary cases and separate hardware/Gazebo gates. This project
has host-only mandatory acceptance; it does not promote autonomous driving or
hardware projects to complete.
