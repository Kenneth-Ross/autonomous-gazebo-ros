#!/usr/bin/env python3
import os
import sys
import numpy as np
import ctypes

def check_rknn_library():
    """Check if librknnrt.so is accessible."""
    lib_name = "librknnrt.so"
    # Common locations
    search_paths = [
        "/usr/lib/" + lib_name,
        "/usr/local/lib/" + lib_name,
        os.path.join(os.getcwd(), "external/rknpu2", lib_name),
        os.path.join(os.path.dirname(__file__), "../../external/rknpu2", lib_name)
    ]
    
    found = False
    for path in search_paths:
        if os.path.exists(path):
            print(f"INFO: Found {lib_name} at {path}")
            found = True
            break
            
    if not found:
        print(f"WARNING: {lib_name} not found in standard paths or workspace.")
        print(f"SUGGESTION: Run 'sudo cp external/rknpu2/librknnrt.so /usr/lib/' on the Orange Pi.")

try:
    from rknnlite.api import RKNNLite
    print("SUCCESS: rknnlite.api imported successfully.")
except ImportError:
    print("FAILURE: rknnlite.api NOT found. You may need to install rknn-toolkit-lite2.")
    sys.exit(1)

def test_inference(model_path):
    check_rknn_library()
    
    if not os.path.exists(model_path):
        print(f"FAILURE: Model file not found at {model_path}")
        return

    rknn = RKNNLite()
    
    print(f"Loading model: {model_path}")
    ret = rknn.load_rknn(model_path)
    if ret != 0:
        print("FAILURE: load_rknn failed.")
        return

    print("Initializing runtime...")
    # Target can be specified for RK3588
    ret = rknn.init_runtime(target='rk3588')
    if ret != 0:
        print("FAILURE: init_runtime failed. Ensure librknnrt.so is in /usr/lib/")
        return

    # Create dummy input (assuming 416x416 RGB for YOLOv11n)
    # Note: Replace with actual model dimensions if different
    img = np.random.randint(0, 255, (416, 416, 3), dtype=np.uint8)
    
    print("Running inference...")
    outputs = rknn.inference(inputs=[img])
    
    if outputs:
        print("SUCCESS: Inference completed.")
        print(f"Number of output tensors: {len(outputs)}")
        for i, out in enumerate(outputs):
            print(f"  Output {i} shape: {out.shape}")
            if len(out.shape) == 3 and out.shape[1] > 80:
                print(f"  NOTE: This looks like a unified 1-tensor YOLO output (channels={out.shape[1]}).")
    else:
        print("FAILURE: Inference returned no results.")

    rknn.release()

if __name__ == '__main__':
    # Try to find the model in the project root
    model_name = "yolo11n_416_qat_int8_fp16out.rknn"
    if not os.path.exists(model_name):
        model_name = os.path.join(os.path.dirname(__file__), "../../", model_name)
        
    test_inference(model_name)
