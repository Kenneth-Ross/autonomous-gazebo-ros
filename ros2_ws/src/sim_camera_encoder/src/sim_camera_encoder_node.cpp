#include <rclcpp/rclcpp.hpp>
#include <image_transport/image_transport.hpp>
#include <cv_bridge/cv_bridge.hpp>
#include <sensor_msgs/msg/image.hpp>

#include <gz/transport/Node.hh>
#include <gz/msgs/image.pb.h>

#include <opencv2/opencv.hpp>
#include <mutex>
#include <memory>

class SimCameraEncoder : public rclcpp::Node {
public:
    SimCameraEncoder() : Node("sim_camera_encoder"), frame_count_(0) {
        rmw_qos_profile_t custom_qos = rmw_qos_profile_default;
        // Create publisher for the combined super-frame with RELIABLE QoS
        // This is required because image_transport republish on the receiving end
        // defaults to RELIABLE and does not expose a parameter to override subscriber QoS.
        pub_ = image_transport::create_publisher(this, "~/super_frame", rmw_qos_profile_default);

        gz_node_ = std::make_unique<gz::transport::Node>();
        
        bool rgb_sub = gz_node_->Subscribe(
            "/oakd/rgbd_camera/image",
            &SimCameraEncoder::OnRGB, this);
            
        bool depth_sub = gz_node_->Subscribe(
            "/oakd/rgbd_camera/depth_image",
            &SimCameraEncoder::OnDepth, this);

        if (!rgb_sub || !depth_sub) {
            RCLCPP_ERROR(this->get_logger(), "Failed to subscribe to Gazebo topics!");
        } else {
            RCLCPP_INFO(this->get_logger(), "Subscribed to Gazebo camera topics.");
        }
    }

private:
    void OnRGB(const gz::msgs::Image &_msg) {
        std::lock_guard<std::mutex> lock(mutex_);
        rgb_msg_ = _msg;
        rgb_ready_ = true;
        ProcessAndPublish();
    }

    void OnDepth(const gz::msgs::Image &_msg) {
        std::lock_guard<std::mutex> lock(mutex_);
        depth_msg_ = _msg;
        depth_ready_ = true;
        ProcessAndPublish();
    }

    void ProcessAndPublish() {
        if (!rgb_ready_ || !depth_ready_) return;

        int64_t rgb_sec = rgb_msg_.header().stamp().sec();
        int64_t rgb_nsec = rgb_msg_.header().stamp().nsec();
        int64_t depth_sec = depth_msg_.header().stamp().sec();
        int64_t depth_nsec = depth_msg_.header().stamp().nsec();

        double diff = std::abs((rgb_sec + rgb_nsec * 1e-9) - (depth_sec + depth_nsec * 1e-9));
        if (diff > 0.05) {
            return;
        }

        cv::Mat rgb(rgb_msg_.height(), rgb_msg_.width(), CV_8UC3, (void*)rgb_msg_.data().c_str());
        cv::cvtColor(rgb, rgb, cv::COLOR_RGB2BGR);

        cv::Mat depth(depth_msg_.height(), depth_msg_.width(), CV_32FC1, (void*)depth_msg_.data().c_str());

        cv::Mat depth_mm;
        depth.convertTo(depth_mm, CV_16UC1, 1000.0);
        
        cv::Mat depth_msb(depth_mm.size(), CV_8UC1);
        cv::Mat depth_lsb(depth_mm.size(), CV_8UC1);
        
        for (int y = 0; y < depth_mm.rows; ++y) {
            const uint16_t* ptr_in = depth_mm.ptr<uint16_t>(y);
            uint8_t* ptr_msb = depth_msb.ptr<uint8_t>(y);
            uint8_t* ptr_lsb = depth_lsb.ptr<uint8_t>(y);
            for (int x = 0; x < depth_mm.cols; ++x) {
                ptr_msb[x] = (ptr_in[x] >> 8) & 0xFF;
                ptr_lsb[x] = ptr_in[x] & 0xFF;
            }
        }

        cv::Mat depth_msb_bgr, depth_lsb_bgr;
        cv::cvtColor(depth_msb, depth_msb_bgr, cv::COLOR_GRAY2BGR);
        cv::cvtColor(depth_lsb, depth_lsb_bgr, cv::COLOR_GRAY2BGR);

        cv::Mat super_frame;
        std::vector<cv::Mat> matrices = {rgb, depth_msb_bgr, depth_lsb_bgr};
        cv::hconcat(matrices, super_frame);

        std_msgs::msg::Header header;
        header.stamp.sec = rgb_sec;
        header.stamp.nanosec = rgb_nsec;
        header.frame_id = "camera_link_optical";

        sensor_msgs::msg::Image::SharedPtr img_msg = cv_bridge::CvImage(header, "bgr8", super_frame).toImageMsg();
        pub_.publish(img_msg);

        rgb_ready_ = false;
        depth_ready_ = false;

        frame_count_++;
        if (frame_count_ % 30 == 0) {
            RCLCPP_INFO(this->get_logger(), "Published Super-Frame %d", frame_count_);
        }
    }

    image_transport::Publisher pub_;
    std::unique_ptr<gz::transport::Node> gz_node_;

    gz::msgs::Image rgb_msg_;
    gz::msgs::Image depth_msg_;
    bool rgb_ready_ = false;
    bool depth_ready_ = false;
    int frame_count_;
    std::mutex mutex_;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    auto node = std::make_shared<SimCameraEncoder>();
    rclcpp::spin(node);
    rclcpp::shutdown();
    return 0;
}
