# Plan: Minimal Car Driving Model (Ackermann)

## Objective:
Implement a minimal driving model for the simulated car in Gazebo that follows Ackermann steering kinematics and responds to steering, brake, and throttle commands.

## Approach:
We will leverage the built-in Gazebo Sim `AckermannSteering` system for kinematics and implement a ROS 2 "Driving Model" node to handle the throttle/brake/steering logic.

## Components:

1.  **Gazebo Ackermann Plugin Integration:**
    *   Modify `car.urdf.xacro` to include the `gz::sim::systems::AckermannSteering` plugin.
    *   Configuration parameters:
        *   `left_joint`: `base_to_left_hinge`
        *   `right_joint`: `base_to_right_hinge`
        *   `rear_left_joint`: `base_to_left_back_wheel`
        *   `rear_right_joint`: `base_to_right_back_wheel`
        *   `wheel_base`: 2.0m
        *   `kingpin_distance`: 1.75m
        *   `wheel_radius`: 0.5m
    *   The plugin will subscribe to `/model/my_robot/cmd_vel` (Gazebo topic).

2.  **ROS 2 Driving Model Node:**
    *   Implement `driving_model_node.py` in `my_gazebo_package`.
    *   **Inputs:**
        *   `/car/throttle` (`std_msgs/msg/Float32`): 0.0 to 1.0.
        *   `/car/brake` (`std_msgs/msg/Float32`): 0.0 to 1.0.
        *   `/car/steering` (`std_msgs/msg/Float32`): -1.0 to 1.0 (mapped to max steering angle).
    *   **Logic:**
        *   Maintain `current_velocity`.
        *   `velocity += (throttle * acceleration - brake * deceleration) * dt`.
        *   Clamp `velocity` within `[min_vel, max_vel]`.
        *   Apply `steering` to compute `steering_angle = steering * max_steering_angle`.
        *   Publish `geometry_msgs/msg/Twist` to `/cmd_vel`.
    *   **Parameters:**
        *   `max_speed`: e.g., 20.0 m/s.
        *   `acceleration`: e.g., 5.0 m/s^2.
        *   `deceleration`: e.g., 10.0 m/s^2 (braking).
        *   `max_steering_angle`: e.g., 0.5 rad (approx 28 degrees).

3.  **ROS-Gazebo Bridge:**
    *   Ensure `/cmd_vel` is bridged from ROS 2 to Gazebo Sim. (Already exists in `gazebo.launch.py`).
    *   Add bridges for the new throttle, brake, and steering topics if external control is needed, or keep them ROS-only.

4.  **Verification:**
    *   Launch simulation and verify that the car responds correctly to manual topic publications:
        *   `ros2 topic pub /car/throttle std_msgs/msg/Float32 "{data: 0.5}"`
        *   `ros2 topic pub /car/steering std_msgs/msg/Float32 "{data: 0.2}"`

## High-Level Steps:

1.  **Modify URDF:** Add `<gazebo>` tags with the Ackermann plugin.
2.  **Create Node:** Develop the Python node for the driving model.
3.  **Update Launch:** Integrate the node into `gazebo.launch.py`.
4.  **Test:** Run and validate.
