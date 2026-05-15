import numpy as np
import cv2
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GLib
import threading
import time

def test_depth_integrity():
    # 1. Create synthetic depth image (1280x800, 16-bit uint)
    width, height = 1280, 800
    # Create a gradient from 500mm to 5000mm
    depth_orig = np.linspace(500, 5000, width * height, dtype=np.uint16).reshape((height, width))
    
    # 2. Bit-split
    msb = (depth_orig >> 8).astype(np.uint8)
    lsb = (depth_orig & 0xFF).astype(np.uint8)
    
    # 3. Create combined frame [RGB (zeros) | MSB | LSB]
    # We use 3840x800
    rgb_dummy = np.zeros((height, width, 3), dtype=np.uint8)
    msb_bgr = cv2.cvtColor(msb, cv2.COLOR_GRAY2BGR)
    lsb_bgr = cv2.cvtColor(lsb, cv2.COLOR_GRAY2BGR)
    
    combined_frame = np.hstack((rgb_dummy, msb_bgr, lsb_bgr))
    
    # 4. GStreamer Pipeline for encoding/decoding
    # We use appsrc -> x264enc -> h264parse -> avdec_h264 -> appsink
    Gst.init(None)
    
    # Try different bitrates
    bitrates = [2000, 12000, 50000]
    
    for bitrate in bitrates:
        print(f"\nTesting with Bitrate: {bitrate} kbps")
        
        pipeline_str = (
            f"appsrc name=src ! videoconvert ! "
            f"x264enc tune=zerolatency speed-preset=ultrafast bitrate={bitrate} ! "
            f"h264parse ! avdec_h264 ! videoconvert ! video/x-raw,format=BGR ! "
            f"appsink name=sink emit-signals=true"
        )
        
        pipeline = Gst.parse_launch(pipeline_str)
        appsrc = pipeline.get_by_name('src')
        appsink = pipeline.get_by_name('sink')
        
        # Set caps for appsrc
        caps = Gst.Caps.from_string(f"video/x-raw,format=BGR,width={width*3},height={height},framerate=30/1")
        appsrc.set_property('caps', caps)
        
        received_frames = []
        cond = threading.Condition()
        
        def on_new_sample(sink):
            sample = sink.emit('pull-sample')
            buf = sample.get_buffer()
            caps = sample.get_caps()
            h = caps.get_structure(0).get_value('height')
            w = caps.get_structure(0).get_value('width')
            
            res, map_info = buf.map(Gst.MapFlags.READ)
            frame = np.frombuffer(map_info.data, dtype=np.uint8).reshape((h, w, 3)).copy()
            buf.unmap(map_info)
            
            with cond:
                received_frames.append(frame)
                cond.notify_all()
            return Gst.FlowReturn.OK

        appsink.connect('new-sample', on_new_sample)
        
        pipeline.set_state(Gst.State.PLAYING)
        
        # Push 5 frames to let the encoder stabilize
        for _ in range(5):
            buf = Gst.Buffer.new_wrapped(combined_frame.tobytes())
            appsrc.emit('push-buffer', buf)
            time.sleep(0.03)
            
        # Wait for at least one frame
        with cond:
            cond.wait_for(lambda: len(received_frames) > 0, timeout=2.0)
            
        if not received_frames:
            print("Failed to receive any frames!")
            pipeline.set_state(Gst.State.NULL)
            continue
            
        decoded_frame = received_frames[-1]
        
        # 5. Reconstruct
        single_w = width
        # Decoded is BGR, so index 0 is Blue
        msb_dec = decoded_frame[:, single_w:2*single_w, 0]
        lsb_dec = decoded_frame[:, 2*single_w:3*single_w, 0]
        
        depth_reconstructed = (msb_dec.astype(np.uint16) << 8) | lsb_dec.astype(np.uint16)
        
        # 6. Analyze error
        error = depth_reconstructed.astype(np.int32) - depth_orig.astype(np.int32)
        abs_error = np.abs(error)
        
        msb_error_count = np.sum(msb_dec != msb)
        lsb_error_count = np.sum(lsb_dec != lsb)
        
        print(f"  MSB pixels changed: {msb_error_count} / {width*height} ({msb_error_count/(width*height)*100:.2f}%)")
        print(f"  LSB pixels changed: {lsb_error_count} / {width*height} ({lsb_error_count/(width*height)*100:.2f}%)")
        print(f"  Max Absolute Error: {np.max(abs_error)} mm")
        print(f"  Mean Absolute Error: {np.mean(abs_error):.2f} mm")
        print(f"  Errors > 250mm (MSB flips): {np.sum(abs_error > 250)}")
        
        pipeline.set_state(Gst.State.NULL)

if __name__ == "__main__":
    test_depth_integrity()
