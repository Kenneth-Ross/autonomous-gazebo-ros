# Gemini Agent Handoff Plan: Video Streaming Receiver

**Objective:** Complete the setup for receiving a GStreamer video stream from a ROS2/Gazebo simulation running on a desktop machine.

**Context:**
*   You are running on an Orange Pi, which is the designated receiving device.
*   The video stream originates from a desktop computer running a Gazebo simulation.
*   The sending ROS2 node (`rgb_image_subscriber`) on the desktop has been modified to use a GStreamer pipeline.
*   This pipeline encodes the video to H.264 and sends it via UDP to this Orange Pi's IP address on port 5000.
*   The desktop-side agent's last action was to hand off the task to you. The primary blocker was authentication issues preventing dependency installation on this device.

**Plan:**

1.  **Verify/Install Dependencies:**
    *   **Goal:** Ensure all necessary GStreamer libraries and Python bindings are installed.
    *   **Action:** Execute a shell command to install the packages. This step may have failed for the previous agent, so it's critical to re-run it. You will need to ask the user for the `sudo` password.
    *   **Command:**
        ```bash
        sudo apt-get update && sudo apt-get install -y python3-gi python3-gst-1.0 gir1.2-gst-plugins-base-1.0 gstreamer1.0-plugins-good gstreamer1.0-plugins-ugly gstreamer1.0-plugins-bad gstreamer1.0-tools
        ```

2.  **Create the Receiver Script:**
    *   **Goal:** Create a Python script to run the GStreamer receiving pipeline.
    *   **Action:** Write the following Python code to a file named `gstreamer_receiver.py`.
    *   **Content:**
        ```python
        #!/usr/bin/env python3
        import gi
        gi.require_version('Gst', '1.0')
        from gi.repository import Gst

        def main():
            # GStreamer pipeline for receiving
            pipeline_str = (
                "udpsrc port=5000 ! "
                "application/x-rtp, encoding-name=H264, payload=96 ! "
                "rtph264depay ! "
                "avdec_h264 ! "
                "videoconvert ! "
                "autovideosink"
            )
            Gst.init(None)
            pipeline = Gst.parse_launch(pipeline_str)
            pipeline.set_state(Gst.State.PLAYING)
            print("GStreamer receiver pipeline started. Waiting for stream...")
            print(f"Pipeline: {pipeline_str}")
            bus = pipeline.get_bus()
            msg = bus.timed_pop_filtered(
                Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS
            )
            if msg:
                if msg.type == Gst.MessageType.ERROR:
                    err, debug_info = msg.parse_error()
                    print(f"Error received from element {msg.src.get_name()}: {err.message}")
                    print(f"Debugging information: {debug_info if debug_info else 'none'}")
                elif msg.type == Gst.MessageType.EOS:
                    print("End-Of-Stream reached.")
            pipeline.set_state(Gst.State.NULL)

        if __name__ == '__main__':
            main()
        ```

3.  **Make Script Executable:**
    *   **Goal:** Ensure the receiver script can be executed.
    *   **Action:** Use the `chmod` command.
    *   **Command:** `chmod +x gstreamer_receiver.py`

4.  **Final Instructions for User:**
    *   **Goal:** Inform the user how to start the entire video stream process.
    *   **Action:** Display a final summary message explaining the steps to be run on both the desktop and the Orange Pi.
    *   **Message:**
        "The setup on the Orange Pi is complete. Here is how to start the video stream:

        **On your Desktop:**

        1.  Open a new terminal.
        2.  Source your ROS2 workspace: `source /home/k-dev/dev/ros2_gazebo/ros2_ws/install/setup.bash`
        3.  Run the Gazebo simulation (e.g., `ros2 launch my_gazebo_package gazebo.launch.py`).
        4.  Open another terminal.
        5.  Source the workspace again: `source /home/k-dev/dev/ros2_gazebo/ros2_ws/install/setup.bash`
        6.  Run the video sender, replacing `<your_orange_pi_ip>` with this device's IP address:
            ```bash
            ros2 run gazebo_oakd_stream_sender rgb_image_subscriber --ros-args -p host:=<your_orange_pi_ip>
            ```

        **On this Orange Pi:**

        1.  Run the receiver script you just created: `./gstreamer_receiver.py`
        2.  A window should appear displaying the video from Gazebo.
        "
