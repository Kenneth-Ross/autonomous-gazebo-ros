# Tutorial: Offloading Gazebo Camera Data to an Edge Device

This tutorial will guide you through the process of adding a camera to your robot in Gazebo and then sending its data over the network to an edge device for processing. This is a common practice for testing robotics algorithms, such as computer vision or SLAM, in a simulated environment before deploying on a real robot.

We will cover:
- Adding a camera sensor to your robot's URDF file.
- Bridging the camera data from Gazebo to ROS2.
- Creating a ROS2 subscriber to receive and process the image data on an edge device.
- Configuring your network for distributed ROS2 communication.

Let's get started!

## Step 1: Update the Robot Model (`car.urdf`)

First, we need to add a camera sensor to your robot's Universal Robot Description Format (URDF) file. This will allow Gazebo to simulate a camera and generate image data.

**1.1. Locate and Edit `car.urdf`**

Open the file `ros2_ws/src/my_gazebo_package/models/car.urdf` in your preferred text editor.

**1.2. Add Gazebo Plugin for Pose Publishing**

Add the following `<gazebo>` block directly after the `<material>` definitions and before the first `<link>` tag. This plugin ensures that model poses are published, which is generally good practice for Gazebo simulations.

```xml
    <gazebo>
      <plugin filename="libignition-gazebo-system-pose-publisher.so" name="ignition::gazebo::systems::PosePublisher">
        <publish_link_pose>true</publish_link_pose>
        <publish_chain_pose>false</publish_chain_pose>
        <publish_visual_pose>false</publish_visual_pose>
        <publish_collision_pose>false</publish_collision_pose>
        <build_graphs>true</build_graphs>
        <rate>100</rate>
        <get_model_state>true</get_model_state>
      </plugin>
    </gazebo>
```

**1.3. Add Camera Link, Joint, and Gazebo Sensor**

Now, add the camera definition. This includes a new `camera_link`, a `camera_joint` to attach it to the `base_link` of your car, and a `<gazebo>` tag that configures the camera sensor plugin. Place this block **just before the closing `</robot>` tag** in your `car.urdf` file.

```xml
    <!-- Camera -->
    <link name="camera_link">
        <visual>
            <geometry>
                <box size="0.05 0.05 0.05"/>
            </geometry>
            <material name="black"/>
        </visual>
        <inertial>
            <mass value="0.1"/>
            <inertia ixx="1e-6" ixy="0" ixz="0" iyy="1e-6" iyz="0" izz="1e-6"/>
        </inertial>
    </link>

    <joint name="camera_joint" type="fixed">
        <parent link="base_link"/>
        <child link="camera_link"/>
        <origin xyz="0.2 0 0.1" rpy="0 0 0"/>
    </joint>

    <gazebo reference="camera_link">
        <sensor type="camera" name="camera_sensor">
            <update_rate>30.0</update_rate>
            <camera name="head">
                <horizontal_fov>1.3962634</horizontal_fov>
                <image>
                    <width>800</width>
                    <height>800</height>
                    <format>R8G8B8</format>
                </image>
                <clip>
                    <near>0.02</near>
                    <far>300</far>
                </clip>
                <noise>
                    <type>gaussian</type>
                    <mean>0.0</mean>
                    <stddev>0.007</stddev>
                </noise>
            </camera>
            <plugin name="camera_controller" filename="libgz-sim-camera.so">
                <camera_topic>/camera</camera_topic>
            </plugin>
        </sensor>
    </gazebo>
```

**1.4. Full `car.urdf` Content**

After these changes, your `car.urdf` file should look like this:

```xml
<?xml version="1.0"?>
<robot name="simplecar">
    <!-- Colors -->
    <material name="black">
        <color rgba="0 0 0 1"/>
    </material>
    <material name="blue">
        <color rgba="0.6 0.7 0.8 1"/>
    </material>

    <gazebo>
      <plugin filename="libignition-gazebo-system-pose-publisher.so" name="ignition::gazebo::systems::PosePublisher">
        <publish_link_pose>true</publish_link_pose>
        <publish_chain_pose>false</publish_chain_pose>
        <publish_visual_pose>false</publish_visual_pose>
        <publish_collision_pose>false</publish_collision_pose>
        <build_graphs>true</build_graphs>
        <rate>100</rate>
        <get_model_state>true</get_model_state>
      </plugin>
    </gazebo>

    <!-- Base Frame of Car -->
    <link name="base_link">
        <visual>
            <geometry>
                <box size="0.5 0.3 0.1"/>
            </geometry>
            <material name="blue"/>
        </visual>
        <inertial>
            <mass value="6"/>
            <inertia ixx="0.2" ixy="0" ixz="0" iyy="0.2" iyz="0.0" izz="0.2"/>
        </inertial>
    </link>


    <!-- Left Front Wheel -->
    <link name="left_front_wheel">
        <visual>
            <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="1.57075 1.57075 0"/>
            <material name="black"/>
        </visual>
        <collision>
             <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="1.57075 1.57075 0"/>
        </collision>
        <inertial>
            <origin rpy="1.57075 1.57075 0"/>
            <mass value="0.3"/>
            <inertia ixx="0.4" ixy="0" ixz="0" iyy="0.4" iyz="0.0" izz="0.2"/>
        </inertial>
    </link>
    <joint name="left_hinge_to_left_front_wheel" type="continuous">
        <parent link="left_hinge"/>
        <child link="left_front_wheel"/>
        <axis xyz="0 1 0"/>
        <origin xyz="0 0.2 0"/>
    </joint>
    <!-- Left Front Wheel - Hinge -->
    <link name="left_hinge">
        <visual>
            <geometry>
                <box size="0.20 0.02 0.02"/>
            </geometry>
            <origin xyz="0 0.1 0 " rpy="0 0 1.57075"/>
            <material name="black"/>
        </visual>
        <inertial>
            <origin rpy="0 0 1.57075"/>
            <mass value="0.01"/>
            <inertia ixx="5E-6" ixy="0" ixz="0" iyy="5E-6" iyz="0" izz="5E-6"/>
        </inertial>
    </link>
    <joint name="base_to_left_hinge" type="revolute">
        <parent link="base_link"/>
        <child link="left_hinge"/>
        <axis xyz="0 0 1"/>
        <origin xyz="0.2 0.0 0"/>
        <limit effort="100" lower="-0.5" upper="0.5" velocity="100"/>
    </joint>
    <!-- Right Front Wheel -->
    <link name="right_front_wheel">
        <visual>
            <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="-1.57075 -1.57075 0"/>
            <material name="black"/>
        </visual>
        <collision>
             <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="-1.57075 -1.57075 0"/>
        </collision>
        <inertial>
            <origin rpy="-1.57075 -1.57075 0"/>
            <mass value="0.3"/>
            <inertia ixx="0.4" ixy="0" ixz="0" iyy="0.4" iyz="0.0" izz="0.2"/>
        </inertial>
    </link>
    <joint name="right_hinge_to_right_front_wheel" type="continuous">
        <parent link="right_hinge"/>
        <child link="right_front_wheel"/>
        <axis xyz="0 1 0"/>
        <origin xyz="0 -0.2 0"/>
    </joint>
    <!-- Right Front Wheel - Hinge -->
    <link name="right_hinge">
        <visual>
            <geometry>
                <box size="0.20 0.02 0.02"/>
            </geometry>
            <origin xyz="0 -0.1 0 " rpy="0 0 -1.57075"/>
            <material name="black"/>
        </visual>
        <inertial>
            <origin rpy="0 0 -1.57075"/>
            <mass value="0.01"/>
            <inertia ixx="5E-6" ixy="0" ixz="0" iyy="5E-6" iyz="0" izz="5E-6"/>
        </inertial>
    </link>
    <joint name="base_to_right_hinge" type="revolute">
        <parent link="base_link"/>
        <child link="right_hinge"/>
        <axis xyz="0 0 1"/>
        <origin xyz="0.2 0 0"/>
        <limit effort="100" lower="-0.5" upper="0.5" velocity="100"/>
    </joint>
    <!-- Left Back Wheel -->
    <link name="left_back_wheel">
        <visual>
            <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="1.57075 1.57075 0"/>
            <material name="black"/>
        </visual>
        <collision>
             <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="1.57075 1.57075 0"/>
        </collision>
        <inertial>
            <origin rpy="1.57075 1.57075 0"/>
            <mass value="0.3"/>
            <inertia ixx="0.4" ixy="0" ixz="0" iyy="0.4" iyz="0.0" izz="0.2"/>
        </inertial>
    </link>
    <joint name="base_to_left_back_wheel" type="continuous">
        <parent link="base_link"/>
        <child link="left_back_wheel"/>
        <axis xyz="0 1 0"/>
        <origin xyz="-0.2 0.175 0"/>
    </joint>
    <!-- Right Back Wheel -->
    <link name="right_back_wheel">
        <visual>
            <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="-1.57075 -1.57075 0"/>
            <material name="black"/>
        </visual>
        <collision>
             <geometry>
                <cylinder length="0.05" radius="0.1"/>
            </geometry>
            <origin rpy="-1.57075 -1.57075 0"/>
        </collision>
        <inertial>
            <origin rpy="-1.57075 -1.57075 0"/>
            <mass value="0.3"/>
            <inertia ixx="0.4" ixy="0" ixz="0" iyy="0.4" iyz="0.0" izz="0.2"/>
        </inertial>
    </link>
    <joint name="base_to_right_back_wheel" type="continuous">
        <parent link="base_link"/>
        <child link="right_back_wheel"/>
        <axis xyz="0 1 0"/>
        <origin xyz="-0.2 -0.175 0"/>
    </joint>

    <!-- Camera -->
    <link name="camera_link">
        <visual>
            <geometry>
                <box size="0.05 0.05 0.05"/>
            </geometry>
            <material name="black"/>
        </visual>
        <inertial>
            <mass value="0.1"/>
            <inertia ixx="1e-6" ixy="0" ixz="0" iyy="1e-6" iyz="0" izz="1e-6"/>
        </inertial>
    </link>

    <joint name="camera_joint" type="fixed">
        <parent link="base_link"/>
        <child link="camera_link"/>
        <origin xyz="0.2 0 0.1" rpy="0 0 0"/>
    </joint>

    <gazebo reference="camera_link">
        <sensor type="camera" name="camera_sensor">
            <update_rate>30.0</update_rate>
            <camera name="head">
                <horizontal_fov>1.3962634</horizontal_fov>
                <image>
                    <width>800</width>
                    <height>800</height>
                    <format>R8G8B8</format>
                </image>
                <clip>
                    <near>0.02</near>
                    <far>300</far>
                </clip>
                <noise>
                    <type>gaussian</type>
                    <mean>0.0</mean>
                    <stddev>0.007</stddev>
                </noise>
            </camera>
            <plugin name="camera_controller" filename="libgz-sim-camera.so">
                <camera_topic>/camera</camera_topic>
            </plugin>
        </sensor>
    </gazebo>
</robot>
