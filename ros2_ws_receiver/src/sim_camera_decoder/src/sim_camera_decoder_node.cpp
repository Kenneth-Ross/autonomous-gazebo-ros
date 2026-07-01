#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include "image_transport/image_transport.hpp"
#include "cv_bridge/cv_bridge.hpp"
#include <opencv2/opencv.hpp>

class SimCameraDecoder : public rclcpp::Node {
public:
    SimCameraDecoder() : Node("ffmpeg_decoder") {
        rgb_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/rgb/image_raw", rclcpp::QoS(rclcpp::KeepLast(10)).best_effort());
        rgb_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/rgb/camera_info", rclcpp::QoS(rclcpp::KeepLast(10)).best_effort());
        depth_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/depth/image_raw", rclcpp::QoS(rclcpp::KeepLast(10)).best_effort());
        depth_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/depth/camera_info", rclcpp::QoS(rclcpp::KeepLast(10)).best_effort());
        
        // Static Camera Info
        static_info_.width = 1280;
        static_info_.height = 800;
        static_info_.k = {800.0, 0.0, 640.0, 0.0, 800.0, 400.0, 0.0, 0.0, 1.0};
        static_info_.p = {800.0, 0.0, 640.0, 0.0, 0.0, 800.0, 400.0, 0.0, 0.0, 0.0, 1.0, 0.0};
        static_info_.r = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
        static_info_.distortion_model = "plumb_bob";
        static_info_.d = {0.0, 0.0, 0.0, 0.0, 0.0};

        // Input subscriber
        sub_ = image_transport::create_subscription(this, "/oakd/super_frame/image_raw", 
            std::bind(&SimCameraDecoder::imageCallback, this, std::placeholders::_1),
            "ffmpeg", rmw_qos_profile_default);
            
        RCLCPP_INFO(this->get_logger(), "Custom FFMPEG Decoder & Unpacker Node Started.");
    }
private:
    void imageCallback(const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
        RCLCPP_INFO_ONCE(this->get_logger(), "Received first decoded frame from ffmpeg!");
        
        cv_bridge::CvImagePtr cv_ptr;
        try {
            cv_ptr = cv_bridge::toCvCopy(msg, "bgr8");
        } catch (cv_bridge::Exception& e) {
            RCLCPP_ERROR(this->get_logger(), "cv_bridge exception: %s", e.what());
            return;
        }

        cv::Mat combined_frame = cv_ptr->image;
        int width = 1280;
        if (combined_frame.cols != width * 3) {
            RCLCPP_ERROR(this->get_logger(), "Unexpected Super-Frame width: %d", combined_frame.cols);
            return;
        }

        cv::Mat rgb_frame = combined_frame(cv::Rect(0, 0, width, combined_frame.rows));
        cv::Mat msb_frame = combined_frame(cv::Rect(width, 0, width, combined_frame.rows));
        cv::Mat lsb_frame = combined_frame(cv::Rect(2*width, 0, width, combined_frame.rows));
        
        cv::Mat msb_gray, lsb_gray;
        cv::extractChannel(msb_frame, msb_gray, 0);
        cv::extractChannel(lsb_frame, lsb_gray, 0);

        cv::Mat depth_16bit(combined_frame.rows, width, CV_16UC1);
        for (int y = 0; y < depth_16bit.rows; ++y) {
            const uint8_t* ptr_msb = msb_gray.ptr<uint8_t>(y);
            const uint8_t* ptr_lsb = lsb_gray.ptr<uint8_t>(y);
            uint16_t* ptr_depth = depth_16bit.ptr<uint16_t>(y);
            for (int x = 0; x < width; ++x) {
                ptr_depth[x] = (static_cast<uint16_t>(ptr_msb[x]) << 8) | static_cast<uint16_t>(ptr_lsb[x]);
            }
        }

        auto header = msg->header;
        header.frame_id = "camera_link_optical";

        sensor_msgs::msg::Image::SharedPtr rgb_msg = cv_bridge::CvImage(header, "bgr8", rgb_frame).toImageMsg();
        sensor_msgs::msg::Image::SharedPtr depth_msg = cv_bridge::CvImage(header, "16UC1", depth_16bit).toImageMsg();

        static_info_.header = header;

        rgb_pub_->publish(*rgb_msg);
        depth_pub_->publish(*depth_msg);
        rgb_info_pub_->publish(static_info_);
        depth_info_pub_->publish(static_info_);
    }

    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr rgb_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr rgb_info_pub_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr depth_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr depth_info_pub_;
    
    image_transport::Subscriber sub_;
    sensor_msgs::msg::CameraInfo static_info_;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SimCameraDecoder>());
    rclcpp::shutdown();
    return 0;
}
