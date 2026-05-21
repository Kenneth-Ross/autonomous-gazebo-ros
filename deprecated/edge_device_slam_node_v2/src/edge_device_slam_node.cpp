#include <memory>
#include <string>
#include <vector>
#include <thread>
#include <iostream>
#include <fstream>

#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/imu.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "visualization_msgs/msg/marker_array.hpp"
#include "cv_bridge/cv_bridge.h"
#include <opencv2/opencv.hpp>

// GStreamer headers
#include <gst/gst.h>
#include <gst/app/gstappsink.h>

// RKNN API
#include "rknn_api.h"

// ORB-SLAM3
#include "System.h"

// Post-processing
#include "edge_device_slam_node/yolo_postprocess.h"

class EdgeDeviceSlamNode : public rclcpp::Node {
public:
    EdgeDeviceSlamNode() : Node("edge_device_slam_node") {
        RCLCPP_INFO(this->get_logger(), "Initializing Edge Device SLAM Node (C++)...");

        // Parameters
        this->declare_parameter("host", "127.0.0.1");
        this->declare_parameter("rgb_port", 5000);
        this->declare_parameter("model_path", "/workspace/yolo11n_416_qat_int8_fp16out.rknn");
        this->declare_parameter("voc_path", "/workspace/ORB_SLAM3/Vocabulary/ORBvoc.txt");
        this->declare_parameter("settings_path", "/workspace/camera_settings.yaml");

        // Initialize ORB-SLAM3
        std::string voc_path = this->get_parameter("voc_path").as_string();
        std::string settings_path = this->get_parameter("settings_path").as_string();
        
        RCLCPP_INFO(this->get_logger(), "Loading ORB-SLAM3 with voc: %s", voc_path.c_str());
        slam_system_ = std::make_unique<ORB_SLAM3::System>(
            voc_path, settings_path, ORB_SLAM3::System::MONOCULAR, false);

        // Subscriptions
        imu_sub_ = this->create_subscription<sensor_msgs::msg::Imu>(
            "/imu", 10, std::bind(&EdgeDeviceSlamNode::imu_callback, this, std::placeholders::_1));
        
        odom_sub_ = this->create_subscription<nav_msgs::msg::Odometry>(
            "/odom", 10, std::bind(&EdgeDeviceSlamNode::odom_callback, this, std::placeholders::_1));

        // Publishers
        image_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge_slam/detections", 10);
        marker_pub_ = this->create_publisher<visualization_msgs::msg::MarkerArray>("/edge_slam/map", 10);

        // Initialize RKNN
        if (init_rknn() != 0) {
            RCLCPP_ERROR(this->get_logger(), "Failed to initialize RKNN.");
        }

        // Initialize GStreamer
        gst_init(nullptr, nullptr);
        setup_gstreamer_pipelines();

        RCLCPP_INFO(this->get_logger(), "Edge SLAM Node initialized and waiting for streams.");
    }

    ~EdgeDeviceSlamNode() {
        stop_gstreamer_pipelines();
        if (ctx > 0) {
            rknn_destroy(ctx);
        }
    }

private:
    int init_rknn() {
        std::string model_path = this->get_parameter("model_path").as_string();
        RCLCPP_INFO(this->get_logger(), "Loading RKNN model from: %s", model_path.c_str());

        // Read model file
        std::ifstream file(model_path, std::ios::binary | std::ios::ate);
        if (!file.is_open()) {
            RCLCPP_ERROR(this->get_logger(), "Could not open model file.");
            return -1;
        }
        std::streamsize size = file.tellg();
        file.seekg(0, std::ios::beg);
        std::vector<char> model_data(size);
        if (!file.read(model_data.data(), size)) {
            return -1;
        }

        int ret = rknn_init(&ctx, model_data.data(), size, 0, NULL);
        if (ret < 0) {
            RCLCPP_ERROR(this->get_logger(), "rknn_init error ret=%d", ret);
            return -1;
        }

        // Query model info
        rknn_sdk_version version;
        rknn_query(ctx, RKNN_QUERY_SDK_VERSION, &version, sizeof(rknn_sdk_version));
        RCLCPP_INFO(this->get_logger(), "RKNN SDK Version: %s", version.api_version);

        return 0;
    }

    static GstFlowReturn on_new_sample(GstAppSink *appsink, gpointer user_data) {
        EdgeDeviceSlamNode *node = static_cast<EdgeDeviceSlamNode*>(user_data);
        GstSample *sample = gst_app_sink_pull_sample(appsink);
        if (sample) {
            GstBuffer *buffer = gst_sample_get_buffer(sample);
            
            // Get timestamp in seconds
            double timestamp = (double)GST_BUFFER_PTS(buffer) / 1e9;
            if (timestamp < 0) timestamp = (double)gst_clock_get_time(gst_system_clock_obtain()) / 1e9;

            GstCaps *caps = gst_sample_get_caps(sample);
            GstStructure *s = gst_caps_get_structure(caps, 0);
            
            int width, height;
            gst_structure_get_int(s, "width", &width);
            gst_structure_get_int(s, "height", &height);

            GstMapInfo map;
            if (gst_buffer_map(buffer, &map, GST_MAP_READ)) {
                cv::Mat frame(height, width, CV_8UC3, (void*)map.data);
                
                // 1. Run RKNN Inference (Detection)
                node->run_inference(frame);

                // 2. Run ORB-SLAM3 Tracking
                Sophus::SE3f Tcw = node->slam_system_->TrackMonocular(frame, timestamp);
                (void)Tcw; // Use pose for further logic (e.g. TF publish)

                gst_buffer_unmap(buffer, &map);
            }
            gst_sample_unref(sample);
        }
        return GST_FLOW_OK;
    }

    void run_inference(cv::Mat &frame) {
        // Pre-processing (Resize to model input size, e.g., 416x416)
        cv::Mat resized_img;
        cv::resize(frame, resized_img, cv::Size(416, 416));

        rknn_input inputs[1];
        memset(inputs, 0, sizeof(inputs));
        inputs[0].index = 0;
        inputs[0].type = RKNN_TENSOR_UINT8;
        inputs[0].size = resized_img.cols * resized_img.rows * resized_img.channels();
        inputs[0].fmt = RKNN_TENSOR_NHWC;
        inputs[0].buf = resized_img.data;

        rknn_inputs_set(ctx, 1, inputs);
        rknn_run(ctx, NULL);

        // Get outputs
        rknn_output outputs[3]; // YOLOv11 usually has 3 output scales
        memset(outputs, 0, sizeof(outputs));
        outputs[0].want_float = 1;
        outputs[1].want_float = 1;
        outputs[2].want_float = 1;
        rknn_outputs_get(ctx, 3, outputs, NULL);

        // Post-process outputs using YoloPostProcess helper
        std::vector<Detection> detections = YoloPostProcess::process(
            (float*)outputs[0].buf, (float*)outputs[1].buf, (float*)outputs[2].buf, 
            frame.cols, frame.rows, 0.5f);
        
        YoloPostProcess::nms(detections, 0.45f);

        for (const auto& det : detections) {
            project_to_3d(det, frame);
            cv::rectangle(frame, det.box, cv::Scalar(0, 255, 0), 2);
        }

        // Publish annotated image
        auto img_msg = cv_bridge::CvImage(std_msgs::msg::Header(), "bgr8", frame).toImageMsg();
        img_msg->header.stamp = this->now();
        image_pub_->publish(*img_msg);
        
        rknn_outputs_release(ctx, 3, outputs);
    }

    void project_to_3d(const Detection& det, const cv::Mat& frame) {
        // Placeholder for 3D projection logic
        (void)det;
        (void)frame;
    }

    void setup_gstreamer_pipelines() {
        int rgb_port = this->get_parameter("rgb_port").as_int();
        // Using mppvideodec for Rockchip hardware acceleration
        std::string pipeline_str = 
            "udpsrc port=" + std::to_string(rgb_port) + " caps=\"application/x-rtp, media=(string)video, clock-rate=(int)90000, encoding-name=(string)H264, payload=(int)96\" ! "
            "rtph264depay ! h264parse ! mppvideodec ! videoconvert ! video/x-raw,format=BGR ! appsink name=sink";

        GError *error = nullptr;
        rgb_pipeline_ = gst_parse_launch(pipeline_str.c_str(), &error);
        if (error) {
            RCLCPP_ERROR(this->get_logger(), "GStreamer parse error: %s", error->message);
            g_error_free(error);
            return;
        }

        GstElement *sink = gst_bin_get_by_name(GST_BIN(rgb_pipeline_), "sink");
        gst_app_sink_set_emit_signals(GST_APP_SINK(sink), TRUE);
        g_signal_connect(sink, "new-sample", G_CALLBACK(on_new_sample), this);
        gst_object_unref(sink);

        gst_element_set_state(rgb_pipeline_, GST_STATE_PLAYING);
    }

    void stop_gstreamer_pipelines() {
        if (rgb_pipeline_) {
            gst_element_set_state(rgb_pipeline_, GST_STATE_NULL);
            gst_object_unref(rgb_pipeline_);
        }
    }

    void imu_callback(const sensor_msgs::msg::Imu::SharedPtr msg) { (void)msg; }
    void odom_callback(const nav_msgs::msg::Odometry::SharedPtr msg) { (void)msg; }

    // ROS 2 Members
    rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
    rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr image_pub_;
    rclcpp::Publisher<visualization_msgs::msg::MarkerArray>::SharedPtr marker_pub_;

    // GStreamer Members
    GstElement *rgb_pipeline_ = nullptr;

    // RKNN Members
    rknn_context ctx = 0;

    // SLAM Members
    std::unique_ptr<ORB_SLAM3::System> slam_system_;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<EdgeDeviceSlamNode>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
