# ROS2 Gazebo Project

This project is a ROS2 package (`my_gazebo_package`) designed for use with Gazebo Harmonic and ROS2 Jetty.

## Structure:
- `launch/`: Contains ROS2 launch files to start Gazebo and load models.
- `models/`: Contains URDF (Unified Robot Description Format) and SDF (Simulation Description Format) files for Gazebo models.
- `worlds/`: Contains SDF files defining Gazebo worlds.
- `my_gazebo_package/`: A Python package for ROS2 nodes or utilities.

## Getting Started:

### Build
To build the package, navigate to the `ros2_ws` directory and use colcon build:
```bash
cd ros2_ws
colcon build --packages-select my_gazebo_package
```

### Source
Before running any ROS2 commands, source the setup files:
```bash
source install/setup.bash
```

### Launch Gazebo
Example of launching Gazebo with a world or model:
```bash
ros2 launch my_gazebo_package gazebo.launch.py
```

### Troubleshooting `ModuleNotFoundError: No module named 'gi'` with Miniconda

If you encounter `ModuleNotFoundError: No module named 'gi'` or `ValueError: Namespace Gst not available` errors when running ROS2 nodes that utilize GStreamer (via `pygobject`), and you are using a Miniconda (or Anaconda) Python environment, it's likely due to Python environment isolation.

**Problem:** Your system might have `python3-gi` and GStreamer development packages installed globally (`sudo apt-get install ...`), but your Miniconda environment uses its own isolated Python interpreter. Therefore, the packages installed globally are not accessible within the Conda environment.

**Solution:** Install `pygobject` and the necessary GStreamer packages directly into your active Conda environment.

1.  **Identify your active Conda environment:**
    ```bash
    conda info --envs
    ```
    (Note the environment marked with `*`, usually `base`).

2.  **Install `pygobject`:**
    ```bash
    conda install -c conda-forge pygobject
    ```

3.  **Install GStreamer core libraries and plugins (including `gst-rtsp-server` if needed for RTSP functionalities):**
    ```bash
    conda install -c conda-forge gstreamer gst-plugins-base gst-plugins-good gst-plugins-bad gst-plugins-ugly gst-rtsp-server
    ```
    Ensure you install `gst-rtsp-server` if your application uses it (like an RTSP streaming server).

After installing these packages, your ROS2 nodes within the Conda environment should be able to find and use `pygobject` and GStreamer.

## Git-Driven Development

This project follows a structured approach for changes using Git:

1.  **Research & Strategy:** Before making changes, analyze the current state of the codebase.
2.  **Task-Based Commits:** Keep commits focused and atomic. Each commit should address a single logical change or bug fix.
3.  **Documentation:** Update markdown files in `docs/` and plans in `plans/` as the project evolves.
4.  **Verification:** Always verify changes by building the workspace (`colcon build`) and running tests before committing.
5.  **Commit Messages:** Use clear, descriptive commit messages that explain *why* a change was made.

Example workflow for a new feature:
- Create a new branch: `git checkout -b feature/new-robot-part`
- Implement changes and update `docs/` or `plans/` if necessary.
- Build and test: `cd ros2_ws && colcon build`
- Stage and commit: `git add . && git commit -m "feat: add new robot part for Gazebo simulation"`