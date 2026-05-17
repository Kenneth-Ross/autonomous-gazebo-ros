#!/usr/bin/env python3
import os
import sys
import numpy as np
import platform
import subprocess

def print_system_info():
    print("--- System Diagnostics ---")
    print(f"OS: {platform.system()}")
    print(f"Machine: {platform.machine()}")
    print(f"Python Version: {sys.version}")
    try:
        model = subprocess.check_output(['cat', '/proc/device-tree/model']).decode().strip()
        print(f"Device Model: {model}")
    except:
        print("Device Model: Unknown (could not read /proc/device-tree/model)")
    print("--------------------------")

def check_rknn_library():
    """Check if librknnrt.so is in /usr/lib/ where the runtime expects it."""
    lib_path = "/usr/lib/librknnrt.so"
    if os.path.exists(lib_path):
        print(f"SUCCESS: Found librknnrt.so at {lib_path}")
        return True
    else:
        print(f"CRITICAL: librknnrt.so NOT found at {lib_path}")
        print("FIX: Run 'sudo cp external/rknpu2/librknnrt.so /usr/lib/ && sudo ldconfig'")
        return False

try:
    from rknnlite.api import RKNNLite
    print("SUCCESS: rknnlite.api imported successfully.")
except ImportError:
    print("FAILURE: rknnlite.api NOT found. You may need to install rknn-toolkit-lite2.")
    sys.exit(1)

def test_inference(model_path):
    print_system_info()
    if not check_rknn_library():
        print("Proceeding anyway, but init_runtime will likely fail...")
    
    if not os.path.exists(model_path):
        print(f"FAILURE: Model file not found at {model_path}")
        return

    rknn = RKNNLite()
    
    print(f"Loading model: {model_path}")
    ret = rknn.load_rknn(model_path)
    if ret != 0:
        print("FAILURE: load_rknn failed.")
        return

    print("Attempting init_runtime (Strategy 1: Auto-detect)...")
    try:
        ret = rknn.init_runtime()
        if ret == 0:
            print("SUCCESS: Runtime initialized via auto-detect.")
        else:
            print(f"Strategy 1 failed with ret={ret}. Trying Strategy 2...")
            raise Exception("Retry")
    except Exception:
        print("Attempting init_runtime (Strategy 2: Explicit RK3588)...")
        try:
            ret = rknn.init_runtime(target='rk3588')
            if ret == 0:
                print("SUCCESS: Runtime initialized with target='rk3588'.")
            else:
                print(f"Strategy 2 failed with ret={ret}.")
                return
        except Exception as e:
            print(f"FAILURE: All init_runtime strategies failed. Error: {e}")
            return

    # Create dummy input (assuming 416x416 RGB for YOLOv11n)
    img = np.random.randint(0, 255, (416, 416, 3), dtype=np.uint8)
    
    print("Running inference...")
    outputs = rknn.inference(inputs=[img])
    
    if outputs:
        print("SUCCESS: Inference completed.")
        for i, out in enumerate(outputs):
            print(f"  Output {i} shape: {out.shape}")
    else:
        print("FAILURE: Inference returned no results.")

    rknn.release()

if __name__ == '__main__':
    model_name = "yolo11n_416_qat_int8_fp16out.rknn"
    if not os.path.exists(model_name):
        model_name = os.path.join(os.path.dirname(__file__), "../../", model_name)
        
    test_inference(model_name)
