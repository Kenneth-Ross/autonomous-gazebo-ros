# [W.I.P] Racing control review fixes

## Goal

Resolve the focused racing-control review findings before Gate A: serialize
supervisor state transitions, bind recorder health to the prepared run, reject
stale or invalid stamped inputs, transform map-frame observations and odometry
through TF at their message times, and keep marker-only quality claims fail-closed.

## Interface and safety behavior

- Keep existing topics and message schemas. Candidates and recorder heartbeats
  must have nonzero, current ROS header stamps; invalid headers do not refresh
  watchdogs. A recorder heartbeat is usable only when its nonempty run ID equals
  the prepared run ID. All participants must use the same ROS clock domain;
  future-stamped messages are rejected because no cross-host clock-skew
  allowance is currently defined.
- Use one mutually exclusive callback group for supervisor timer, subscriptions,
  and lifecycle services.
- Transform map-frame cones into `base_link` at the map stamp before left/right
  classification. Transform odometry pose into the path frame at the odometry
  stamp before control. Missing, old, or extrapolated TF produces an invalid
  control candidate and therefore zero output through the supervisor.
- Only accept a cone when its `last_observed` time is also current and finite;
  cap every cone score by finite localization confidence in `[0, 1]`.
- `visualization_msgs/MarkerArray` does not provide measured detector,
  association, depth, and pose quality. The adapter marks such estimates with
  zero confidence and `QUARANTINED`; the planner ignores them. Racing remains
  stopped until a typed, quality-bearing source replaces the marker adapter.

## Acceptance

Automated host coverage must include matching and mismatched recorder IDs,
stale/future/zero stamps, nominal transformed corridor geometry, missing TF,
and a node-level nominal/adversarial supervisor pass (healthy matching recorder
plus valid command; abort/mismatch/stale input always outputs zero). Preserve
the test output as evidence. Run a clean package-scoped Jazzy build/test where
available. Orange Pi deployment and fixed/unseen-track safe-lap acceptance
remain separate gates; do not promote Autonomous Racing beyond `[W.I.P]` here.

## Progress

- [x] Initial audit and focused scope recorded.
- [x] Add run-ID and source-stamp API regressions before corresponding fixes;
  expand automated coverage to transformed corridor, missing TF, missing
  localization, marker quarantine, matching/mismatched recorder, stale
  candidates, and abort.
- [x] Implement fixes and pass package-scoped host build/tests.
- [x] Record node-level nominal and adversarial evidence; list edge checks still
  required.

## Retained host evidence

See [RACING_REVIEW_FIXES_HOST.md](../docs/evidence/RACING_REVIEW_FIXES_HOST.md)
for the package commands and nominal/adversarial node-level results. End-to-end
Orange Pi Gate A and fixed/unseen-track acceptance are still required.
The regressions pass, but a separate pre-fix failing run was not retained.

## Independent regression replay

[Retained comparison](../docs/evidence/RACING_REVIEW_REGRESSION_REPLAY.md):
both new node regressions fail against original `e18157b2` production binaries
and pass against the patched package. This retrospective replay does not claim
an initial TDD red run. The parent independently reran the fixed core and node
acceptance after handoff. Deployment, trusted cone-source integration, and
Orange Pi safe-lap evidence remain open, so status stays `[W.I.P]`.
