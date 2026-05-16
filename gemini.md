# ROS 2 Gazebo Project (Ubuntu 24.04 / ROS 2 Jazzy)

This project is a hybrid ROS 2 system designed for high-performance robotics simulation and edge offloading. It utilizes **ROS 2 Jazzy Jalisco** on **Ubuntu 24.04**.

## Architecture Overview
- **Gazebo Host (`ros2_ws/`):** Runs Gazebo Harmonic, robot controllers, and the **Virtual OAK-D Super-Frame Sender**.
- **Edge Receiver (`ros2_ws_receiver/`):** Runs on hardware (e.g., Orange Pi 5) for **VPU-accelerated decoding** (`hevc_rkmpp`), Depth Unpacking, and RTAB-Map SLAM.
- **Streaming:** High-fidelity 16-bit Depth + RGB streaming via **FFmpeg Image Transport** using a vertical Super-Frame (1280x2400).

## Virtual OAK-D Super-Frame
To replicate OAK-D hardware specs and ensure perfect temporal synchronization:
1. **Vertical Stacking**: RGB (top), MSB Depth (middle), and LSB Depth (bottom) are stacked into a single frame.
2. **Luminance Protection**: Depth slices are replicated across BGR channels to utilize the full-resolution Luminance (Y) channel in HEVC, protecting 16-bit precision from lossy chroma subsampling.
3. **Synchronized Unpacking**: The receiver slices the frame and publishes RGB and 16-bit Depth with identical timestamps.

## Semantic Mapping & RKNN NPU Acceleration
The project is currently transitioning from geometric SLAM to **Semantic SLAM** by leveraging the RK3588 NPU:
1. **Accelerated Inference**: Using `rknpu2` and RKNN-converted YOLOv11 models to detect racing cones at 30+ FPS.
2. **3D Projection**: 2D bounding boxes are projected into 3D space using the synchronized 16-bit depth from the Virtual OAK-D pipeline.
3. **Landmark Injection**: Cones are injected into RTAB-Map as persistent landmarks (via `User Data` or `Landmark` topics) to enhance loop closure and create a labeled race track map.
4. **Robust Distance Calculation**: Implementation of a 5x5 window average on depth ROI to handle sensor noise and depth "holes" at object boundaries.

## Project Structure:
- `ros2_ws/`: Simulation workspace (Gazebo worlds, models, and sender nodes).
- `ros2_ws_receiver/`: Edge device workspace (unpacker nodes, SLAM bridge).
- `docs/`: Technical specifications and tutorials.
- `scripts/`: Automated setup and deployment tools.

## Getting Started:

### 1. Build the Workspaces
**Simulation Host:**
```bash
cd ros2_ws
colcon build --symlink-install
```

**Edge Device:**
```bash
cd ros2_ws_receiver
sudo colcon build --symlink-install --merge-install
```

### 2. Networking (CycloneDDS)
The project requires `rmw_cyclonedds_cpp`. 
- **Interface:** Configure your active network interface in `ros2_ws_receiver/src/rtabmap_bridge/config/cyclonedds.xml`.

### 3. Launching
- **Sim Host:** `ros2 launch gazebo_oakd_stream_sender stream_to_remote.launch.py`
- **Edge Device:** `ros2 launch rtabmap_bridge rtabmap_slam.launch.py`

## Git Worktrees

The project utilizes **Git Worktrees** to maintain multiple active environments or specialized versions (e.g., `foxglove_worktree/`) without switching branches in the main directory.

- **Primary Development:** Conducted in the project root.
- **Specialized Environments:** Managed via worktrees to ensure isolation of build artifacts and configurations.
- **Exclusion:** Specialized worktrees are typically added to `.gitignore` to prevent recursive tracking.

To add a new worktree:
```bash
git worktree add ../new_feature_branch feature/new_feature
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