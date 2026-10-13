# E2E test consolidation — retained host results

Date: 2026-10-12, simulation-server local time. Scope: test consolidation on
Ubuntu/Jazzy; no production-node behavior change in this consolidation. Earlier
uncommitted racing fixes and documentation work remain preserved. No Orange Pi
or full Gazebo run was performed here.

## Migration of 28 cases

| Removed cases | Count | Replacement or reason |
|---|---:|---|
| Ordinary core planner/controller/supervisor units | 10 | Connected production-node graph verifies observable planning, commands, lifecycle, recorder interlock, fault latching, and confidence |
| Python prototype command-gate units | 5 | Production launch uses C++; test the actual production supervisor |
| Python source-string racing launch assertions | 4 | Actual nodes exchange generated message/service types and assert sole final-command publisher; unused prototype source checks are removed |
| Message-file substring/placeholder checks | 2 | Canonical message package compiles in both workspaces; E2E uses real generated messages/services and serialization |
| Recorder fake executable/file-shape units | 5 | Production RPCs launch real rosbag2 MCAP; metadata, exact payload/frame/timestamp playback, allowlist, and terminal artifacts are checked |
| Pure actuator slew/full-lock units | 2 | Existing production actuator node acceptance verifies physical output and reversal timing |

Core units shrink from 14 to four; recorder artifact units shrink from six to
one. Driving-model units retain the five exact timeout-boundary cases. Counts
refer to the working tree immediately before consolidation, including the
previous review fixes. Codec/depth, perception geometry, file-safety, and remaining
camera/vehicle/configuration checks are preserved.

## Execution evidence

- Red phase: added a connected-flow regression to the original disconnected
  harness. Existing methods passed; the new method failed because no real
  controller candidate reached the supervisor. Retained output below.
- Green phase: removed the controller-output remap, made the production graph
  fully connected, and moved fixtures to its sensor/recorder boundaries. The
  connected graph passed before removing redundant units.
- Real recorder acceptance passed before removing fake-recorder/file-shape units.
  COMPLETE and ABORTED runs were replayed from MCAP with exact payloads, frame IDs,
  source timestamps, counts, and forbidden-topic exclusion.
- Builds passed for `autonomous_racing_msgs` in both workspaces,
  `autonomous_racing_core` on the host edge workspace, and `my_gazebo_package`.
- `ctest --test-dir edge_stack/build/autonomous_racing_core -LE e2e --output-on-failure`:
  **7/7** entries passed (four C++ cases plus six lint suites).
- `ctest --test-dir server_sim/build/my_gazebo_package -LE e2e --output-on-failure`:
  **5/5** entries passed (11 retained Python cases across five files).
- `scripts/validation/racing_host_e2e.sh`: **three E2E suites passed**. Connected
  racing has four scenario methods and a shutdown check; recorder has a lifecycle
  method with COMPLETE/ABORTED subcases and shutdown; actuator has a runtime method
  and shutdown. Nine launch-test methods passed in total.
- New Python acceptance files passed flake8; shell syntax and `git diff --check`
  passed. No package installation, commit, or push occurred.

The final default runner retained CTest logs under `validation_evidence/` with
run ID `20261013T021936Z-39147`. During development, the playback CLI required an
integer acknowledgment timeout, and the registered runner exposed stale/new bag
subscription discovery. Both were corrected: the test observes current command
and heartbeat subscriptions and their teardown before proceeding. It does not
hide missing recorded topics with retries or omit the assertion.

## Boundaries still unverified

These are host control, storage, and actuator E2E boundaries with synthetic cone,
odometry, and heartbeat inputs. No nominal path/candidate is manufactured by the
control fixture. Real recording is a separate suite. Camera-to-edge transport,
NPU perception, a sensor-to-wheel vehicle lap, and Orange Pi Gate A remain their
existing separate acceptance gates. Marker-only input still cannot authorize
motion; a trusted typed cone source must replace it.

## Red connected-flow output

```text
[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-19-06-36-822746-k-dev-ubuntu-desktop-31953
[INFO] [launch]: Default logging verbosity is set to INFO
test_connected_control_pipeline (autonomous_racing_core.TestRacingNodes.test_connected_control_pipeline) ... [INFO] [racing_supervisor_node-1]: process started with pid [31969]
[INFO] [racing_planner_node-2]: process started with pid [31970]
[INFO] [racing_controller_node-3]: process started with pid [31971]
[INFO] [cone_map_adapter_node-4]: process started with pid [32019]
[racing_supervisor_node-1] [INFO] [1791857196.864110266] [racing_supervisor_acceptance]: racing supervisor ready
[racing_supervisor_node-1] [INFO] [1791857196.884174061] [racing_supervisor_acceptance]: supervisor timer active
[racing_supervisor_node-1] [INFO] [1791857197.048747533] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857197.048777232] [racing_supervisor_acceptance]: prepare callback completed
[racing_controller_node-3] [WARN] [1791857197.145551553] [racing_controller_acceptance]: odometry transform unavailable: "map" passed to lookupTransform argument target_frame does not exist.
FAIL
test_supervisor_nominal_and_adversarial_faults_zero_output (autonomous_racing_core.TestRacingNodes.test_supervisor_nominal_and_adversarial_faults_zero_output) ... [racing_supervisor_node-1] [INFO] [1791857198.806519157] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857198.806550767] [racing_supervisor_acceptance]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857198.884507075] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857198.884526584] [racing_supervisor_acceptance]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857198.944493200] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857198.944504800] [racing_supervisor_acceptance]: prepare callback completed
ok
test_transformed_corridor_and_controller_tf (autonomous_racing_core.TestRacingNodes.test_transformed_corridor_and_controller_tf) ... [racing_planner_node-2] [WARN] [1791857199.282254980] [racing_planner_acceptance]: cone map transform unavailable: "missing_map" passed to lookupTransform argument source_frame does not exist.
[racing_controller_node-3] [WARN] [1791857199.305548529] [racing_controller_acceptance]: odometry transform unavailable: "missing_odom" passed to lookupTransform argument source_frame does not exist.
ok

======================================================================
FAIL: test_connected_control_pipeline (autonomous_racing_core.TestRacingNodes.test_connected_control_pipeline)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/k-dev/dev/ros2_gazebo/edge_stack/src/autonomous_racing_core/test/test_racing_nodes_launch.py", line 342, in test_connected_control_pipeline
    assert any(command.twist.linear.x > 0.5 for command in self.commands), (
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: trusted cone-map input must reach final control through production nodes

----------------------------------------------------------------------
Ran 3 tests in 2.466s

FAILED (failures=1)
[INFO] [cone_map_adapter_node-4]: sending signal 'SIGINT' to process[cone_map_adapter_node-4]
[INFO] [racing_controller_node-3]: sending signal 'SIGINT' to process[racing_controller_node-3]
[INFO] [racing_planner_node-2]: sending signal 'SIGINT' to process[racing_planner_node-2]
[INFO] [racing_supervisor_node-1]: sending signal 'SIGINT' to process[racing_supervisor_node-1]
[cone_map_adapter_node-4] [INFO] [1791857199.310433102] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_controller_node-3] [INFO] [1791857199.310620779] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_planner_node-2] [INFO] [1791857199.310775077] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_supervisor_node-1] [INFO] [1791857199.311177861] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[INFO] [cone_map_adapter_node-4]: process has finished cleanly [pid 32019]
[INFO] [racing_controller_node-3]: process has finished cleanly [pid 31971]
[INFO] [racing_planner_node-2]: process has finished cleanly [pid 31970]
[INFO] [racing_supervisor_node-1]: process has finished cleanly [pid 31969]

----------------------------------------------------------------------
Ran 0 tests in 0.000s

NO TESTS RAN

```

## Green connected-control output

```text
-- run_test.py: extra environment variables:
 - ROS_DOMAIN_ID=178
-- run_test.py: invoking following command in '/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core':
 - /usr/bin/python3 -m launch_testing.launch_test /home/k-dev/dev/ros2_gazebo/edge_stack/src/autonomous_racing_core/test/test_racing_e2e_launch.py --junit-xml=/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core/test_results/autonomous_racing_core/test_test_racing_e2e_launch.py.xunit.xml --package-name=autonomous_racing_core

[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-19-19-36-552827-k-dev-ubuntu-desktop-39170
[INFO] [launch]: Default logging verbosity is set to INFO
test_connected_control_pipeline_and_explicit_lifecycle (autonomous_racing_core.TestRacingE2E.test_connected_control_pipeline_and_explicit_lifecycle) ... [INFO] [racing_supervisor_node-1]: process started with pid [39193]
[INFO] [racing_planner_node-2]: process started with pid [39194]
[INFO] [racing_controller_node-3]: process started with pid [39195]
[INFO] [cone_map_adapter_node-4]: process started with pid [39196]
[racing_supervisor_node-1] [INFO] [1791857976.593083547] [e2e_supervisor]: racing supervisor ready
[racing_supervisor_node-1] [INFO] [1791857976.613144273] [e2e_supervisor]: supervisor timer active
[racing_supervisor_node-1] [INFO] [1791857976.864627219] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857976.864658309] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857977.333982701] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857977.334009020] [e2e_supervisor]: prepare callback completed
ok
test_marker_only_observations_cannot_authorize_motion (autonomous_racing_core.TestRacingE2E.test_marker_only_observations_cannot_authorize_motion) ... [racing_supervisor_node-1] [INFO] [1791857980.355003351] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857980.355044880] [e2e_supervisor]: prepare callback completed
ok
test_recorder_and_candidate_faults_latch_zero_output (autonomous_racing_core.TestRacingE2E.test_recorder_and_candidate_faults_latch_zero_output) ... [racing_supervisor_node-1] [INFO] [1791857983.372930380] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857983.372972059] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857983.614158215] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857983.614195965] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857983.895412464] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857983.895441293] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857984.153623889] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857984.153648329] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857984.395351353] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857984.395369363] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857984.653897351] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857984.653923700] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857985.375150615] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857985.375164625] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857985.634203711] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857985.634281819] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857985.895903191] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857985.895916361] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857986.153933278] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857986.153971347] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857986.395498574] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857986.395539344] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857986.653983671] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857986.653997570] [e2e_supervisor]: prepare callback completed
ok
test_sensor_and_path_faults_stop_the_connected_graph (autonomous_racing_core.TestRacingE2E.test_sensor_and_path_faults_stop_the_connected_graph) ... [racing_supervisor_node-1] [INFO] [1791857989.423027047] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857989.423069976] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857989.675342921] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857989.675369361] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857989.955251692] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857989.955282902] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857990.233965758] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857990.233993377] [e2e_supervisor]: prepare callback completed
[racing_planner_node-2] [WARN] [1791857990.355158341] [e2e_planner]: cone map transform unavailable: "missing_map" passed to lookupTransform argument source_frame does not exist.
[racing_controller_node-3] [WARN] [1791857990.374757586] [e2e_controller]: odometry transform unavailable: "missing_map" passed to lookupTransform argument target_frame does not exist.
[racing_supervisor_node-1] [INFO] [1791857990.513914127] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857990.513943156] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857990.974025928] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857990.974040867] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857991.253633172] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857991.253668821] [e2e_supervisor]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791857991.515194599] [e2e_supervisor]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791857991.515230538] [e2e_supervisor]: prepare callback completed
ok

----------------------------------------------------------------------
Ran 4 tests in 15.393s

OK
[INFO] [cone_map_adapter_node-4]: sending signal 'SIGINT' to process[cone_map_adapter_node-4]
[INFO] [racing_controller_node-3]: sending signal 'SIGINT' to process[racing_controller_node-3]
[INFO] [racing_planner_node-2]: sending signal 'SIGINT' to process[racing_planner_node-2]
[INFO] [racing_supervisor_node-1]: sending signal 'SIGINT' to process[racing_supervisor_node-1]
[cone_map_adapter_node-4] [INFO] [1791857991.959601791] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_controller_node-3] [INFO] [1791857991.959837356] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_planner_node-2] [INFO] [1791857991.960018102] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_supervisor_node-1] [INFO] [1791857991.960342705] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[INFO] [cone_map_adapter_node-4]: process has finished cleanly [pid 39196]
[INFO] [racing_planner_node-2]: process has finished cleanly [pid 39194]
[INFO] [racing_supervisor_node-1]: process has finished cleanly [pid 39193]
[INFO] [racing_controller_node-3]: process has finished cleanly [pid 39195]
test_all_production_nodes_exit_cleanly (autonomous_racing_core.TestRacingShutdown.test_all_production_nodes_exit_cleanly) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK


-- run_test.py: return code 0
-- run_test.py: verify result file '/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core/test_results/autonomous_racing_core/test_test_racing_e2e_launch.py.xunit.xml'

```

## Real MCAP lifecycle/playback output

```text
-- run_test.py: extra environment variables:
 - ROS_DOMAIN_ID=177
-- run_test.py: invoking following command in '/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package':
 - /usr/bin/python3 -m launch_testing.launch_test /home/k-dev/dev/ros2_gazebo/server_sim/src/my_gazebo_package/test/test_run_recorder_e2e_launch.py --junit-xml=/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package/test_results/my_gazebo_package/test_test_run_recorder_e2e_launch.py.xunit.xml --package-name=my_gazebo_package

[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-19-19-57-969071-k-dev-ubuntu-desktop-39340
[INFO] [launch]: Default logging verbosity is set to INFO
test_real_mcap_lifecycle_and_rejected_requests (my_gazebo_package.TestRecorderE2E.test_real_mcap_lifecycle_and_rejected_requests) ... [INFO] [run_recorder_node.py-1]: process started with pid [39347]
[run_recorder_node.py-1] [INFO] [1791857998.309803383] [e2e_run_recorder]: prepare request received: run_id_hint='../escape' active=False
[run_recorder_node.py-1] [ERROR] [1791857998.310002899] [e2e_run_recorder]: run recorder prepare failed: run_id must be 1-64 safe filename characters
[run_recorder_node.py-1] [INFO] [1791857998.310626016] [e2e_run_recorder]: prepare request received: run_id_hint='e2e-complete' active=False
[run_recorder_node.py-1] [INFO] [1791857998.311503727] [e2e_run_recorder]: recorder process started: run_id='e2e-complete'
[run_recorder_node.py-1] [INFO] [1791857998.311672473] [e2e_run_recorder]: prepare response ready: run_id='e2e-complete'
[run_recorder_node.py-1] [INFO] [1791857998.311960067] [e2e_run_recorder]: prepare request received: run_id_hint='e2e-complete' active=True
RECORDER E2E COMPLETE: {'/car/control_request': 20, '/racing/recorder/heartbeat': 4}; payload replayed; allowlist enforced
[run_recorder_node.py-1] [INFO] [1791858000.443095000] [e2e_run_recorder]: prepare request received: run_id_hint='e2e-aborted' active=False
[run_recorder_node.py-1] [INFO] [1791858000.444428192] [e2e_run_recorder]: recorder process started: run_id='e2e-aborted'
[run_recorder_node.py-1] [INFO] [1791858000.444646447] [e2e_run_recorder]: prepare response ready: run_id='e2e-aborted'
[run_recorder_node.py-1] [INFO] [1791858000.445009460] [e2e_run_recorder]: prepare request received: run_id_hint='e2e-aborted' active=True
ok

----------------------------------------------------------------------
Ran 1 test in 4.670s

OK
RECORDER E2E ABORTED: {'/car/control_request': 21, '/racing/recorder/heartbeat': 5}; payload replayed; allowlist enforced
[INFO] [run_recorder_node.py-1]: sending signal 'SIGINT' to process[run_recorder_node.py-1]
[INFO] [run_recorder_node.py-1]: process has finished cleanly [pid 39347]
test_clean_exit_and_remove_test_scratch (my_gazebo_package.TestRecorderShutdown.test_clean_exit_and_remove_test_scratch) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK


-- run_test.py: return code 0
-- run_test.py: verify result file '/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package/test_results/my_gazebo_package/test_test_run_recorder_e2e_launch.py.xunit.xml'

```

## Production actuator output

```text
-- run_test.py: extra environment variables:
 - ROS_DOMAIN_ID=176
-- run_test.py: invoking following command in '/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package':
 - /usr/bin/python3 -m launch_testing.launch_test /home/k-dev/dev/ros2_gazebo/server_sim/src/my_gazebo_package/test/test_driving_model_runtime.py --junit-xml=/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package/test_results/my_gazebo_package/test_test_driving_model_runtime.py.xunit.xml --package-name=my_gazebo_package

[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-19-19-52-491291-k-dev-ubuntu-desktop-39302
[INFO] [launch]: Default logging verbosity is set to INFO
test_safety_and_actuator_runtime_contract (my_gazebo_package.TestDrivingModelRuntime.test_safety_and_actuator_runtime_contract) ... [INFO] [driving_model_node.py-1]: process started with pid [39316]
[driving_model_node.py-1] [INFO] [1791857992.729707817] [driving_model]: Driving Model Node (v11 - Closed-Loop & Watchdog Fix) started.
[driving_model_node.py-1] [WARN] [1791857992.924499728] [driving_model]: WATCHDOG TRIGGERED: No commands for 0.20s. Emergency Braking.
[driving_model_node.py-1] [WARN] [1791857993.674914080] [driving_model]: WATCHDOG TRIGGERED: No commands for 0.23s. Emergency Braking.
[driving_model_node.py-1] [WARN] [1791857994.025157864] [driving_model]: WATCHDOG TRIGGERED: No commands for 0.22s. Emergency Braking.
[driving_model_node.py-1] [INFO] [1791857994.724922637] [driving_model]: Heartbeat: V_msr=0.00, V_tgt=0.00, Steer=0.00
[driving_model_node.py-1] [INFO] [1791857996.724986678] [driving_model]: Heartbeat: V_msr=0.00, V_tgt=0.00, Steer=-0.67
ok

----------------------------------------------------------------------
Ran 1 test in 4.904s

OK
[INFO] [driving_model_node.py-1]: sending signal 'SIGINT' to process[driving_model_node.py-1]
[INFO] [driving_model_node.py-1]: process has finished cleanly [pid 39316]
test_clean_exit (my_gazebo_package.TestDrivingModelShutdown.test_clean_exit) ... ok

----------------------------------------------------------------------
Ran 1 test in 0.000s

OK


-- run_test.py: return code 0
-- run_test.py: verify result file '/home/k-dev/dev/ros2_gazebo/server_sim/build/my_gazebo_package/test_results/my_gazebo_package/test_test_driving_model_runtime.py.xunit.xml'

```
