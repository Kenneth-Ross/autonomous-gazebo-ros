#!/usr/bin/env python3
import rclpy
from rclpy.node import Node
from sensor_msgs.msg import Image
from vision_msgs.msg import Detection2DArray, Detection2D, ObjectHypothesisWithPose
from cv_bridge import CvBridge
from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy, DurabilityPolicy
import numpy as np
import cv2
import os

try:
    from rknnlite.api import RKNNLite
    RKNN_AVAILABLE = True
except ImportError:
    RKNN_AVAILABLE = False

class ConeDetectorNPUNode(Node):
    def __init__(self):
        super().__init__('cone_detector_npu')
        self.br = CvBridge()
        
        # Declare parameters
        self.declare_parameter('model_path', '/home/k-dev/dev/ros2_gazebo/yolo11n_416_qat_int8_fp16out.rknn')
        self.declare_parameter('conf_threshold', 0.5)
        self.declare_parameter('nms_threshold', 0.4)
        
        self.model_path = self.get_parameter('model_path').value
        self.conf_threshold = self.get_parameter('conf_threshold').value
        self.nms_threshold = self.get_parameter('nms_threshold').value
        
        # Initialize RKNN
        if not RKNN_AVAILABLE:
            self.get_logger().error("rknnlite Python package is NOT available on this system! Inference will not run.")
            self.rknn = None
        else:
            self.rknn = RKNNLite()
            self.get_logger().info(f"Loading RKNN model from: {self.model_path}")
            if not os.path.exists(self.model_path):
                self.get_logger().error(f"RKNN model file does not exist at: {self.model_path}")
                self.rknn = None
            else:
                ret = self.rknn.load_rknn(self.model_path)
                if ret != 0:
                    self.get_logger().error("Failed to load RKNN model.")
                    self.rknn = None
                else:
                    # Attempt to initialize runtime on RK3588 NPU
                    try:
                        ret = self.rknn.init_runtime(target='rk3588')
                        if ret == 0:
                            self.get_logger().info("RKNN runtime initialized successfully on RK3588 NPU.")
                        else:
                            self.get_logger().error(f"Failed to init_runtime with ret={ret}.")
                            self.rknn = None
                    except Exception as e:
                        self.get_logger().error(f"Exception initializing RKNN runtime: {e}")
                        self.rknn = None
        
        # QoS Profile matching the unpacker node (best effort for high-bandwidth images)
        pipeline_qos = QoSProfile(
            reliability=ReliabilityPolicy.BEST_EFFORT,
            history=HistoryPolicy.KEEP_LAST,
            depth=10,
            durability=DurabilityPolicy.VOLATILE
        )
        
        # Publisher for detections
        self.det_pub = self.create_publisher(Detection2DArray, '/yolo/detections', 10)
        
        # Subscriptions
        self.img_sub = self.create_subscription(
            Image,
            '/camera/rgb/image_raw',
            self.image_callback,
            pipeline_qos
        )
        
        self.get_logger().info("Cone Detector NPU Node initialized.")

    def image_callback(self, msg):
        if self.rknn is None:
            self.get_logger().warn("RKNN runtime is not initialized. Skipping frame.")
            return
            
        try:
            cv_img = self.br.imgmsg_to_cv2(msg, "bgr8")
        except Exception as e:
            self.get_logger().error(f"Failed to convert ROS image: {e}")
            return
            
        orig_h, orig_w = cv_img.shape[:2]
        
        # Preprocessing: resize to 416x416 RGB (NHWC format)
        resized_img = cv2.resize(cv_img, (416, 416))
        input_data = cv2.cvtColor(resized_img, cv2.COLOR_BGR2RGB)
        input_data_4d = np.expand_dims(input_data, axis=0) # Shape: (1, 416, 416, 3)
        
        # Inference
        try:
            outputs = self.rknn.inference(inputs=[input_data_4d])
        except Exception as e:
            self.get_logger().error(f"RKNN inference failed: {e}")
            return
            
        if not outputs or len(outputs) == 0:
            return
            
        # Parse output: shape is (1, 5, 3549)
        output_tensor = np.squeeze(outputs[0]) # Shape: (5, 3549)
        output_tensor = output_tensor.T # Shape: (3549, 5)
        
        # [cx, cy, w, h, conf]
        cx = output_tensor[:, 0]
        cy = output_tensor[:, 1]
        w = output_tensor[:, 2]
        h = output_tensor[:, 3]
        conf = output_tensor[:, 4]
        
        # Filter by confidence
        mask = conf > self.conf_threshold
        cx = cx[mask]
        cy = cy[mask]
        w = w[mask]
        h = h[mask]
        conf = conf[mask]
        
        # Map to original image coordinates
        x1 = (cx - w / 2) / 416.0 * orig_w
        y1 = (cy - h / 2) / 416.0 * orig_h
        x2 = (cx + w / 2) / 416.0 * orig_w
        y2 = (cy + h / 2) / 416.0 * orig_h
        
        boxes = []
        for i in range(len(x1)):
            boxes.append([int(x1[i]), int(y1[i]), int(x2[i] - x1[i]), int(y2[i] - y1[i])])
            
        confidences = conf.tolist()
        
        # Run NMS
        indices = cv2.dnn.NMSBoxes(boxes, confidences, self.conf_threshold, self.nms_threshold)
        
        # Build Detection2DArray message
        det_array_msg = Detection2DArray()
        det_array_msg.header = msg.header # Keep same timestamp and frame id
        
        if len(indices) > 0:
            # OpenCV 4.x NMSBoxes can return shape like (N, 1) or flat list depending on version
            flat_indices = np.array(indices).flatten()
            for idx in flat_indices:
                box = boxes[idx]
                score = confidences[idx]
                
                det = Detection2D()
                det.header = msg.header
                
                # Setup bbox
                det.bbox.center.x = float(box[0] + box[2] / 2.0)
                det.bbox.center.y = float(box[1] + box[3] / 2.0)
                det.bbox.size_x = float(box[2])
                det.bbox.size_y = float(box[3])
                
                # Add hypothesis
                hyp = ObjectHypothesisWithPose()
                hyp.hypothesis.class_id = "cone"
                hyp.hypothesis.score = float(score)
                det.results.append(hyp)
                
                det_array_msg.detections.append(det)
                
        self.det_pub.publish(det_array_msg)

    def __del__(self):
        if hasattr(self, 'rknn') and self.rknn is not None:
            self.rknn.release()

def main(args=None):
    rclpy.init(args=args)
    node = ConeDetectorNPUNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

if __name__ == '__main__':
    main()
