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

    # Initialize GStreamer
    Gst.init(None)

    # Create the pipeline
    pipeline = Gst.parse_launch(pipeline_str)

    # Start playing
    pipeline.set_state(Gst.State.PLAYING)

    print("GStreamer receiver pipeline started. Waiting for stream...")
    print(f"Pipeline: {pipeline_str}")

    # Wait until error or EOS
    bus = pipeline.get_bus()
    msg = bus.timed_pop_filtered(
        Gst.CLOCK_TIME_NONE, Gst.MessageType.ERROR | Gst.MessageType.EOS
    )

    # Parse message
    if msg:
        if msg.type == Gst.MessageType.ERROR:
            err, debug_info = msg.parse_error()
            print(f"Error received from element {msg.src.get_name()}: {err.message}")
            print(f"Debugging information: {debug_info if debug_info else 'none'}")
        elif msg.type == Gst.MessageType.EOS:
            print("End-Of-Stream reached.")
        else:
            # This should not happen
            print(f"Unexpected message received: {msg.type}")

    # Free resources
    pipeline.set_state(Gst.State.NULL)

if __name__ == '__main__':
    main()
