# Active Project Audit

This is the authoritative portfolio-level progress ledger. Every active project must have one of these exact statuses in both this table and its specification title:

- `[PLAN]`: scope, requirements, interfaces, acceptance criteria, and risks are being specified; implementation has not started.
- `[W.I.P]`: implementation is active against an approved specification using test-driven development (red → green → refactor).
- `[VERIFICATION]`: planned implementation and automated acceptance tests are complete enough to run nominal and adversarial verification; any unresolved result blocks completion.
- `[COMPLETE]`: nominal and adversarial acceptance criteria passed and evidence is retained in [VALIDATION.md](VALIDATION.md) or a project-specific evidence section.

Status changes and material progress must update this ledger in the same change as the relevant specification, code, or evidence. Source presence alone cannot advance a project to `[COMPLETE]`.

## Portfolio

| Status | Project | Specification | Current progress | Next gate |
|---|---|---|---|---|
| `[W.I.P]` | Simulation-to-edge RGB-D streaming | [Streaming contract](STREAMING_CONTRACT.md) | Sole C++ producer; configurable C++ decoder; host sender packages and server-side decoder compile | Add automated contract and adversarial harnesses, then complete Orange Pi depth-error, rate, latency, loss, restart, and sustained-run verification |
| `[W.I.P]` | Autonomous racing | [Autonomous racing plan](autonomous_racing_plan.md) | Controller, reactive planner, validator, telemetry recorder, orchestrator, launch files, and track services exist | Implement remaining path-planning and integration milestones, add behavioral tests, and run the documented end-to-end lifecycle |
| `[PLAN]` | Autonomous navigation acceptance | [Autonomous testing plan](AUTONOMOUS_TESTING_PLAN.md) | Test procedures drafted; no retained pass record | Review timing and safety thresholds against current code, then execute Phase 1 |
| `[W.I.P]` | Foxglove edge visualization | [Foxglove integration](FOXGLOVE_INTEGRATION.md) | Bridge, whitelist, ground-truth broadcaster, and static transforms are present in the edge launch | Add automated whitelist/launch tests and an adversarial access/failure harness, then verify on the Orange Pi |
| `[W.I.P]` | Edge RTAB-Map localization and mapping | **Current specification required** | Decoder, RGB-D odometry, EKF, RTAB-Map container, and launch configuration exist | Write a current spec from the live launch and define mapping/localization acceptance criteria |
| `[W.I.P]` | Semantic cone perception and landmarks | **Current specification required** | RKNN detector and landmark projection nodes exist | Write a current spec, pin model/runtime inputs, add deterministic projection tests, and retain Orange Pi inference evidence |
| `[W.I.P]` | Edge Nav2 and control bridge | **Current specification required** | Nav2 configuration and Ackermann bridge exist | Write a current spec and verify command, limit, watchdog, and failure behavior |

## Project-spec requirements

A project specification must contain:

1. objective and non-goals;
2. current-state baseline;
3. functional and non-functional requirements;
4. host/edge ownership and interfaces;
5. parameters, topics, frames, formats, and failure behavior;
6. implementation milestones with checkable progress;
7. acceptance criteria and exact verification commands;
8. risks, compatibility, deployment, and rollback notes;
9. links to retained evidence when entering `[VERIFICATION]` or `[COMPLETE]`.

## Test-driven development and verification gates

- Every behavior change starts with a failing automated test that expresses the specification, then the minimum implementation to pass, followed by refactoring with the suite green.
- Bug fixes require a regression test that fails before the fix.
- A project cannot enter `[VERIFICATION]` with only manual procedures; its deterministic requirements need automated acceptance tests. Hardware-only properties may use automated harnesses that collect device evidence.
- Verification runs the nominal acceptance suite and adversarial passes covering invalid/malformed input, boundary values, timing and ordering faults, packet/message loss, process and device restart, dependency/network unavailability, resource pressure, and safe shutdown/recovery where applicable.
- Every adversarial case records expected failure behavior, observed behavior, evidence, and verdict. Unexpected success is not a pass unless the specification permits it.
- `[COMPLETE]` requires all required nominal and adversarial cases to pass, with no skipped mandatory test and no unresolved critical/high defect.


A status label is not evidence. `[COMPLETE]` requires every nominal and adversarial acceptance criterion to have a recorded verdict; partial, skipped, or hardware-blocked verification stays `[VERIFICATION]`.

## Audit cadence

Update this ledger whenever:

- a project is proposed, paused, resumed, split, merged, or retired;
- a milestone or acceptance criterion changes;
- implementation begins or reaches feature-complete state;
- verification produces a pass, failure, regression, or environmental blocker;
- current documentation is moved to `deprecated/`.
