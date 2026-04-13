import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstRtspServer', '1.0')
from gi.repository import Gst, GstRtspServer, GLib
import sys

def main():
    try:
        Gst.init(None)
        server = GstRtspServer.RTSPServer()
        server.set_service("8554") # Using a hardcoded port for testing

        factory = GstRtspServer.RTSPMediaFactory()
        launch_string = "( videotestsrc ! vp8enc ! rtpvp8pay name=pay0 pt=96 )"
        factory.set_launch(launch_string)
        factory.set_shared(True)

        mount_points = server.get_mount_points()
        mount_points.add_factory("/test", factory) # Using a hardcoded stream name for testing

        server.attach(None)
        print("GStreamer RTSP server initialized successfully.")

        loop = GLib.MainLoop()
        loop.run()

    except Exception as e:
        print(f"Error initializing GStreamer RTSP server: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()