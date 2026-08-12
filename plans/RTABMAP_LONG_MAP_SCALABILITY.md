# [PLAN] RTAB-Map Long-Map Scalability

Priority: Low.

## Observation

Bounded 120-second SLAM acceptance passes. During one continuous mapping session,
working memory grew to 418 nodes and delay p95 reached 575 ms, exceeding the
500 ms operational target. Camera pairing and message conversion remained healthy.

## Investigation

- Capture RTAB-Map processing and delay at working-memory sizes 100, 200, 300,
  400, and 500.
- Measure graph optimization, loop-closure, local-map, publication, CPU, and RSS.
- Test working-memory and local-graph bounds one parameter at a time.
- Verify loop closure, localization, landmark stability, and map quality do not
  regress.

## Acceptance

Expected maximum-duration mapping session maintains delay p95 below 500 ms with
bounded memory and no loss of loop closure or localization quality.
