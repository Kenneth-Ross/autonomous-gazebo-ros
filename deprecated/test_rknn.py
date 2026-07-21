import cv2
import numpy as np
import os
import sys

try:
    from rknnlite.api import RKNNLite
except ImportError:
    print("Error: rknnlite not installed.")
    sys.exit(1)

def test_yolo():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    model_path = os.path.join(script_dir, 'yolo11n_416_qat_int8_fp16out.rknn')
    img_path = os.path.join(script_dir, 'test_image.jpg')
    
    if not os.path.exists(model_path):
        print(f"Model not found: {model_path}")
        return
        
    if not os.path.exists(img_path):
        print(f"Image not found: {img_path}")
        return

    print("Initializing RKNNLite...")
    rknn = RKNNLite()
    ret = rknn.load_rknn(model_path)
    if ret != 0:
        print("Failed to load RKNN model.")
        return
        
    ret = rknn.init_runtime()
    if ret != 0:
        print("Failed to init runtime.")
        return

    print("Loading image...")
    cv_img = cv2.imread(img_path)
    orig_h, orig_w = cv_img.shape[:2]
    
    # Preprocessing
    resized_img = cv2.resize(cv_img, (416, 416))
    input_data = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
    input_data_4d = np.expand_dims(input_data, axis=0)
    
    print("Running inference...")
    outputs = rknn.inference(inputs=[input_data_4d])
    
    if not outputs or len(outputs) == 0:
        print("Inference returned empty output.")
        return
        
    output_tensor = np.squeeze(outputs[0])
    output_tensor = output_tensor.T
    
    cx = output_tensor[:, 0]
    cy = output_tensor[:, 1]
    w = output_tensor[:, 2]
    h = output_tensor[:, 3]
    conf = output_tensor[:, 4]
    
    print(f"Max confidence in tensor: {np.max(conf):.4f}")
    
    # Filter
    mask = conf > 0.1
    print(f"Boxes above 0.1 conf: {np.sum(mask)}")
    
    mask = conf > 0.5
    print(f"Boxes above 0.5 conf: {np.sum(mask)}")
    
    rknn.release()

if __name__ == '__main__':
    test_yolo()
