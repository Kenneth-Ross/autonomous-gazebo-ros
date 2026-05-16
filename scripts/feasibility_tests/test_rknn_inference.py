#!/usr/bin/env python3
import os
import sys
import numpy as np

try:
    from rknnlite.api import RKNNLite
    print("SUCCESS: rknnlite.api imported successfully.")
except ImportError:
    print("FAILURE: rknnlite.api NOT found. You may need to install rknn-toolkit-lite2.")
    sys.exit(1)

def test_inference(model_path):
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
    ret = rknn.init_runtime()
    if ret != 0:
        print("FAILURE: init_runtime failed.")
        return

    # Create dummy input (assuming 416x416 RGB)
    img = np.random.randint(0, 255, (416, 416, 3), dtype=np.uint8)
    
    print("Running inference...")
    outputs = rknn.inference(inputs=[img])
    
    if outputs:
        print("SUCCESS: Inference completed. Output shapes:")
        for i, out in enumerate(outputs):
            print(f"  Output {i}: {out.shape}")
    else:
        print("FAILURE: Inference returned no results.")

    rknn.release()

if __name__ == '__main__':
    # Default path relative to repo root
    default_model = "yolo11n_416_qat_int8_fp16out.rknn"
    test_inference(default_model)
