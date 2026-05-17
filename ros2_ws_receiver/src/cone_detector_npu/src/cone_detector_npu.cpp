#include <rclcpp/rclcpp.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <vision_msgs/msg/detection2_d_array.hpp>
#include <cv_bridge/cv_bridge.hpp>
#include <opencv2/opencv.hpp>
#include "rknn_api.h"
#include <fstream>
#include <vector>

class ConeDetectorNpu : public rclcpp::Node {
public:
    ConeDetectorNpu() : Node("cone_detector_npu"), ctx(0) {
        this->declare_parameter("model_path", "");
        this->declare_parameter("confidence_threshold", 0.5);
        this->declare_parameter("nms_threshold", 0.45);

        std::string model_path = this->get_parameter("model_path").as_string();
        if (model_path.empty()) {
            RCLCPP_ERROR(this->get_logger(), "Model path not provided!");
            return;
        }

        if (init_rknn(model_path) != 0) {
            RCLCPP_ERROR(this->get_logger(), "Failed to initialize RKNN!");
            return;
        }

        subscription_ = this->create_subscription<sensor_msgs::msg::Image>(
            "/camera/rgb/image_raw", 10,
            std::bind(&ConeDetectorNpu::image_callback, this, std::placeholders::_1));

        publisher_ = this->create_publisher<vision_msgs::msg::Detection2DArray>(
            "/cone_detections", 10);

        RCLCPP_INFO(this->get_logger(), "Cone Detector NPU Node initialized with model: %s", model_path.c_str());
    }

    ~ConeDetectorNpu() {
        if (ctx > 0) {
            rknn_destroy(ctx);
        }
    }

private:
    int init_rknn(const std::string& model_path) {
        // Load model data
        std::ifstream file(model_path, std::ios::binary | std::ios::ate);
        if (!file.is_open()) return -1;
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
        std::vector<char> buffer(size);
        if (!file.read(buffer.data(), size)) return -1;

        int ret = rknn_init(&ctx, buffer.data(), size, 0, NULL);
        if (ret < 0) return ret;

        // Query SDK version
        rknn_sdk_version sdk_ver;
        rknn_query(ctx, RKNN_QUERY_SDK_VERSION, &sdk_ver, sizeof(sdk_ver));
        RCLCPP_INFO(this->get_logger(), "RKNN SDK Version: %s", sdk_ver.api_version);

        // Get input/output information
        rknn_input_output_num io_num;
        rknn_query(ctx, RKNN_QUERY_IN_OUT_NUM, &io_num, sizeof(io_num));
        
        input_attrs.resize(io_num.n_input);
        for (uint32_t i = 0; i < io_num.n_input; i++) {
            input_attrs[i].index = i;
            rknn_query(ctx, RKNN_QUERY_INPUT_ATTR, &input_attrs[i], sizeof(rknn_tensor_attr));
        }

        output_attrs.resize(io_num.n_output);
        for (uint32_t i = 0; i < io_num.n_output; i++) {
            output_attrs[i].index = i;
            rknn_query(ctx, RKNN_QUERY_OUTPUT_ATTR, &output_attrs[i], sizeof(rknn_tensor_attr));
        }

        if (io_num.n_output != 1) {
            RCLCPP_WARN(this->get_logger(), "Expected 1 output tensor, but found %d. Ensure your YOLO export is correct.", io_num.n_output);
        }

        return 0;
    }

    void image_callback(const sensor_msgs::msg::Image::SharedPtr msg) {
        cv_bridge::CvImagePtr cv_ptr;
        try {
            cv_ptr = cv_bridge::toCvCopy(msg, sensor_msgs::image_encodings::BGR8);
        } catch (cv_bridge::Exception& e) {
            RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
            return;
        }

        cv::Mat frame = cv_ptr->image;
        int img_width = frame.cols;
        int img_height = frame.rows;

        // Pre-processing (Resize to model input size, e.g., 640x640 or 416x416)
        int model_w = input_attrs[0].dims[2]; // Assuming NHWC
        int model_h = input_attrs[0].dims[1];
        cv::Mat resized_img;
        cv::resize(frame, resized_img, cv::Size(model_w, model_h));
        cv::cvtColor(resized_img, resized_img, cv::COLOR_BGR2RGB);

        rknn_input inputs[1];
        memset(inputs, 0, sizeof(inputs));
        inputs[0].index = 0;
        inputs[0].type = RKNN_TENSOR_UINT8;
        inputs[0].size = resized_img.cols * resized_img.rows * resized_img.channels();
        inputs[0].fmt = RKNN_TENSOR_NHWC;
        inputs[0].buf = resized_img.data;

        ret = rknn_inputs_set(ctx, 1, inputs);
        if (ret < 0) {
            RCLCPP_ERROR(this->get_logger(), "rknn_inputs_set error ret=%d", ret);
            return;
        }

        ret = rknn_run(ctx, NULL);
        if (ret < 0) {
            RCLCPP_ERROR(this->get_logger(), "rknn_run error ret=%d", ret);
            return;
        }

        // Get outputs
        rknn_output outputs[1];
        memset(outputs, 0, sizeof(outputs));
        outputs[0].want_float = 1;
        ret = rknn_outputs_get(ctx, 1, outputs, NULL);
        if (ret < 0) {
            RCLCPP_ERROR(this->get_logger(), "rknn_outputs_get error ret=%d", ret);
            return;
        }

        // Post-processing for 1-tensor output: [1, 5, 3549]
        // Format: [0:cx, 1:cy, 2:w, 3:h, 4:score] (Single class model)
        float* data = (float*)outputs[0].buf;
        int num_anchors = output_attrs[0].dims[2];  // 3549
        float conf_threshold = this->get_parameter("confidence_threshold").as_double();
        float nms_threshold = this->get_parameter("nms_threshold").as_double();
        
        std::vector<vision_msgs::msg::Detection2D> candidate_dets;

        for (int i = 0; i < num_anchors; i++) {
            float score = data[4 * num_anchors + i]; // Score is at channel index 4

            if (score > conf_threshold) {
                vision_msgs::msg::Detection2D det;
                float cx = data[0 * num_anchors + i] * img_width / model_w;
                float cy = data[1 * num_anchors + i] * img_height / model_h;
                float w = data[2 * num_anchors + i] * img_width / model_w;
                float h = data[3 * num_anchors + i] * img_height / model_h;

                det.bbox.center.position.x = cx;
                det.bbox.center.position.y = cy;
                det.bbox.size_x = w;
                det.bbox.size_y = h;
                
                vision_msgs::msg::ObjectHypothesisWithPose hyp;
                hyp.hypothesis.class_id = "0"; // Cone
                hyp.hypothesis.score = score;
                det.results.push_back(hyp);
                
                candidate_dets.push_back(det);
            }
        }

        // Apply Non-Maximum Suppression (NMS)
        std::sort(candidate_dets.begin(), candidate_dets.end(), [](const auto& a, const auto& b) {
            return a.results[0].hypothesis.score > b.results[0].hypothesis.score;
        });

        vision_msgs::msg::Detection2DArray det_array;
        det_array.header = msg->header;
        std::vector<bool> is_suppressed(candidate_dets.size(), false);

        for (size_t i = 0; i < candidate_dets.size(); ++i) {
            if (is_suppressed[i]) continue;
            det_array.detections.push_back(candidate_dets[i]);

            for (size_t j = i + 1; j < candidate_dets.size(); ++j) {
                if (is_suppressed[j]) continue;
                
                // Calculate Intersection over Union (IoU)
                auto& b1 = candidate_dets[i].bbox;
                auto& b2 = candidate_dets[j].bbox;
                
                float x1 = std::max(b1.center.position.x - b1.size_x/2, b2.center.position.x - b2.size_x/2);
                float y1 = std::max(b1.center.position.y - b1.size_y/2, b2.center.position.y - b2.size_y/2);
                float x2 = std::min(b1.center.position.x + b1.size_x/2, b2.center.position.x + b2.size_x/2);
                float y2 = std::min(b1.center.position.y + b1.size_y/2, b2.center.position.y + b2.size_y/2);
                
                float inter_area = std::max(0.0f, x2 - x1) * std::max(0.0f, y2 - y1);
                float union_area = b1.size_x * b1.size_y + b2.size_x * b2.size_y - inter_area;
                
                if (inter_area / union_area > nms_threshold) {
                    is_suppressed[j] = true;
                }
            }
        }
        
        publisher_->publish(det_array);
        rknn_outputs_release(ctx, 1, outputs);
    }

    rknn_context ctx;
    int ret;
    std::vector<rknn_tensor_attr> input_attrs;
    std::vector<rknn_tensor_attr> output_attrs;
    rclcpp::Subscription<sensor_msgs::msg::Image>::SharedPtr subscription_;
    rclcpp::Publisher<vision_msgs::msg::Detection2DArray>::SharedPtr publisher_;
};

int main(int argc, char** argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<ConeDetectorNpu>());
    rclcpp::shutdown();
    return 0;
}
