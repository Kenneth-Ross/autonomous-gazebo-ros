# Original-code regression replay — 2026-10-12

The parent reviewer extracted `autonomous_racing_core` from Git `HEAD`
(`e18157b2`) into a temporary source/build/install prefix and compiled its original
production binaries against Jazzy and the existing message dependencies. The
new launch regression file then ran against those binaries on `ROS_DOMAIN_ID=179`,
with the temporary ament/library prefix first. No working-tree source or branch
was reverted. Build/install here refers to isolated colcon/CMake artifacts;
no system package was installed.

The same two ROS test methods failed against original code: the recorder-ID
fault status was absent, and the translated/rotated map corridor did not produce
the expected centerline. The launcher exited 1 with two failures and no errors.
This replay happened **after implementation**; it proves regression sensitivity
and does not replace the missing initial TDD red run.

The parent then sourced the fixed edge workspace and independently reran:

```bash
ctest --test-dir edge_stack/build/autonomous_racing_core -R '^test_' --output-on-failure
```

Both CTest entries passed: 14 C++ cases and two ROS-node cases.
The green node acceptance retained nominal motion and adversarial stop scenarios.
No Orange Pi execution, Gazebo safe-lap run, or race-detector pass is claimed.

## Original-code launch output

```text
[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-18-59-31-438867-k-dev-ubuntu-desktop-31225
[INFO] [launch]: Default logging verbosity is set to INFO
test_supervisor_nominal_and_adversarial_faults_zero_output (autonomous_racing_core.TestRacingNodes.test_supervisor_nominal_and_adversarial_faults_zero_output) ... [INFO] [racing_supervisor_node-1]: process started with pid [31241]
[INFO] [racing_planner_node-2]: process started with pid [31242]
[INFO] [racing_controller_node-3]: process started with pid [31243]
[INFO] [cone_map_adapter_node-4]: process started with pid [31286]
[racing_supervisor_node-1] [INFO] [1791856771.480807040] [racing_supervisor_acceptance]: racing supervisor ready
[racing_supervisor_node-1] [INFO] [1791856771.500873811] [racing_supervisor_acceptance]: supervisor timer active
[racing_supervisor_node-1] [INFO] [1791856771.665353296] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791856771.665374306] [racing_supervisor_acceptance]: prepare callback completed
FAIL
test_transformed_corridor_and_controller_tf (autonomous_racing_core.TestRacingNodes.test_transformed_corridor_and_controller_tf) ... FAIL

======================================================================
FAIL: test_supervisor_nominal_and_adversarial_faults_zero_output (autonomous_racing_core.TestRacingNodes.test_supervisor_nominal_and_adversarial_faults_zero_output)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/k-dev/dev/ros2_gazebo/edge_stack/src/autonomous_racing_core/test/test_racing_nodes_launch.py", line 283, in test_supervisor_nominal_and_adversarial_faults_zero_output
    assert self.spin_until(lambda: self.commands and self.commands[-1].twist.linear.x == 0.0
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

======================================================================
FAIL: test_transformed_corridor_and_controller_tf (autonomous_racing_core.TestRacingNodes.test_transformed_corridor_and_controller_tf)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/home/k-dev/dev/ros2_gazebo/edge_stack/src/autonomous_racing_core/test/test_racing_nodes_launch.py", line 202, in test_transformed_corridor_and_controller_tf
    assert self.spin_until(lambda: any(
           ^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError

----------------------------------------------------------------------
Ran 2 tests in 8.525s

FAILED (failures=2)
[INFO] [cone_map_adapter_node-4]: sending signal 'SIGINT' to process[cone_map_adapter_node-4]
[INFO] [racing_controller_node-3]: sending signal 'SIGINT' to process[racing_controller_node-3]
[INFO] [racing_planner_node-2]: sending signal 'SIGINT' to process[racing_planner_node-2]
[INFO] [racing_supervisor_node-1]: sending signal 'SIGINT' to process[racing_supervisor_node-1]
[cone_map_adapter_node-4] [INFO] [1791856779.985722771] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_controller_node-3] [INFO] [1791856779.985916000] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_planner_node-2] [INFO] [1791856779.986078270] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_supervisor_node-1] [INFO] [1791856779.986267070] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[INFO] [racing_planner_node-2]: process has finished cleanly [pid 31242]
[INFO] [racing_controller_node-3]: process has finished cleanly [pid 31243]
[INFO] [cone_map_adapter_node-4]: process has finished cleanly [pid 31286]
[INFO] [racing_supervisor_node-1]: process has finished cleanly [pid 31241]

----------------------------------------------------------------------
Ran 0 tests in 0.000s

NO TESTS RAN

```

## Fixed-code launch output

```text
-- run_test.py: extra environment variables:
 - ROS_DOMAIN_ID=178
-- run_test.py: invoking following command in '/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core':
 - /usr/bin/python3 -m launch_testing.launch_test /home/k-dev/dev/ros2_gazebo/edge_stack/src/autonomous_racing_core/test/test_racing_nodes_launch.py --junit-xml=/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core/test_results/autonomous_racing_core/test_test_racing_nodes_launch.py.xunit.xml --package-name=autonomous_racing_core

[INFO] [launch]: All log files can be found below /home/k-dev/.ros/log/2026-10-12-18-59-57-765054-k-dev-ubuntu-desktop-31375
[INFO] [launch]: Default logging verbosity is set to INFO
test_supervisor_nominal_and_adversarial_faults_zero_output (autonomous_racing_core.TestRacingNodes.test_supervisor_nominal_and_adversarial_faults_zero_output) ... [INFO] [racing_supervisor_node-1]: process started with pid [31392]
[INFO] [racing_planner_node-2]: process started with pid [31393]
[INFO] [racing_controller_node-3]: process started with pid [31394]
[INFO] [cone_map_adapter_node-4]: process started with pid [31442]
[racing_supervisor_node-1] [INFO] [1791856797.805698021] [racing_supervisor_acceptance]: racing supervisor ready
[racing_supervisor_node-1] [INFO] [1791856797.825767061] [racing_supervisor_acceptance]: supervisor timer active
[racing_supervisor_node-1] [INFO] [1791856797.990529857] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791856797.990542007] [racing_supervisor_acceptance]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791856798.066045545] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791856798.066053945] [racing_supervisor_acceptance]: prepare callback completed
[racing_supervisor_node-1] [INFO] [1791856798.126080371] [racing_supervisor_acceptance]: prepare callback entered
[racing_supervisor_node-1] [INFO] [1791856798.126102391] [racing_supervisor_acceptance]: prepare callback completed
ok
test_transformed_corridor_and_controller_tf (autonomous_racing_core.TestRacingNodes.test_transformed_corridor_and_controller_tf) ... [racing_planner_node-2] [WARN] [1791856798.463452580] [racing_planner_acceptance]: cone map transform unavailable: "missing_map" passed to lookupTransform argument source_frame does not exist.
[racing_controller_node-3] [WARN] [1791856798.487452068] [racing_controller_acceptance]: odometry transform unavailable: "missing_odom" passed to lookupTransform argument source_frame does not exist.
ok

----------------------------------------------------------------------
Ran 2 tests in 0.713s

OK
[INFO] [cone_map_adapter_node-4]: sending signal 'SIGINT' to process[cone_map_adapter_node-4]
[INFO] [racing_controller_node-3]: sending signal 'SIGINT' to process[racing_controller_node-3]
[INFO] [racing_planner_node-2]: sending signal 'SIGINT' to process[racing_planner_node-2]
[INFO] [racing_supervisor_node-1]: sending signal 'SIGINT' to process[racing_supervisor_node-1]
[cone_map_adapter_node-4] [INFO] [1791856798.492002336] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_controller_node-3] [INFO] [1791856798.492204566] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_planner_node-2] [INFO] [1791856798.492506545] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[racing_supervisor_node-1] [INFO] [1791856798.492743394] [rclcpp]: signal_handler(SIGINT/SIGTERM)
[INFO] [cone_map_adapter_node-4]: process has finished cleanly [pid 31442]
[INFO] [racing_planner_node-2]: process has finished cleanly [pid 31393]
[INFO] [racing_controller_node-3]: process has finished cleanly [pid 31394]
[INFO] [racing_supervisor_node-1]: process has finished cleanly [pid 31392]

----------------------------------------------------------------------
Ran 0 tests in 0.000s

NO TESTS RAN


-- run_test.py: return code 0
-- run_test.py: verify result file '/home/k-dev/dev/ros2_gazebo/edge_stack/build/autonomous_racing_core/test_results/autonomous_racing_core/test_test_racing_nodes_launch.py.xunit.xml'

```
