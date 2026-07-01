#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include "image_transport/image_transport.hpp"
#include "cv_bridge/cv_bridge.hpp"
#include <opencv2/opencv.hpp>
#include "sensor_msgs/msg/compressed_image.hpp"

#include "rclcpp_components/register_node_macro.hpp"

class SimCameraDecoder : public rclcpp::Node {
public:
    SimCameraDecoder(const rclcpp::NodeOptions & options = rclcpp::NodeOptions()) 
    : Node("ffmpeg_decoder", options), last_published_time_(0, 0, this->get_clock()->get_clock_type()) {
        rgb_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/rgb/image_raw", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        rgb_compressed_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>("/edge/camera/rgb/image_raw/compressed", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        rgb_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/rgb/camera_info", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        depth_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/depth/image_raw", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        depth_compressed_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>("/edge/camera/depth/image_raw/compressed", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        depth_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/depth/camera_info", rclcpp::QoS(rclcpp::KeepLast(2)).best_effort());
        
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
            
        RCLCPP_INFO(this->get_logger(), "Custom FFMPEG Decoder & Unpacker Node Started. Throttling output to ~5 FPS.");
    }
private:
    void imageCallback(const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
        // Throttle to ~5 FPS (0.2 seconds between frames)
        rclcpp::Time current_time(msg->header.stamp);
        if (current_time.seconds() == 0.0) {
             current_time = this->now();
        }
        
        if (last_published_time_.seconds() != 0.0 && (current_time - last_published_time_).seconds() < 0.2) {
            return; // Skip frame
        }
        last_published_time_ = current_time;

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

        auto rgb_msg = std::make_unique<sensor_msgs::msg::Image>();
        cv_bridge::CvImage(header, "bgr8", rgb_frame).toImageMsg(*rgb_msg);
        auto depth_msg = std::make_unique<sensor_msgs::msg::Image>();
        cv_bridge::CvImage(header, "16UC1", depth_16bit).toImageMsg(*depth_msg);

        static_info_.header = header;

        rgb_pub_->publish(std::move(rgb_msg));
        depth_pub_->publish(std::move(depth_msg));
        
        auto rgb_comp_msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
        rgb_comp_msg->header = header;
        rgb_comp_msg->format = "jpeg";
        cv::imencode(".jpg", rgb_frame, rgb_comp_msg->data, {cv::IMWRITE_JPEG_QUALITY, 50});
        rgb_compressed_pub_->publish(std::move(rgb_comp_msg));

        auto depth_comp_msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
        depth_comp_msg->header = header;
        depth_comp_msg->format = "png";
        cv::imencode(".png", depth_16bit, depth_comp_msg->data, {cv::IMWRITE_PNG_COMPRESSION, 3});
        depth_compressed_pub_->publish(std::move(depth_comp_msg));

        auto info_msg1 = std::make_unique<sensor_msgs::msg::CameraInfo>(static_info_);
        rgb_info_pub_->publish(std::move(info_msg1));
        
        auto info_msg2 = std::make_unique<sensor_msgs::msg::CameraInfo>(static_info_);
        depth_info_pub_->publish(std::move(info_msg2));
    }

    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr rgb_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr rgb_compressed_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr rgb_info_pub_;
    rclcpp::Publisher<sensor_msgs::msg::Image>::SharedPtr depth_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr depth_compressed_pub_;
    rclcpp::Publisher<sensor_msgs::msg::CameraInfo>::SharedPtr depth_info_pub_;
    
    image_transport::Subscriber sub_;
    sensor_msgs::msg::CameraInfo static_info_;
    rclcpp::Time last_published_time_;
};

RCLCPP_COMPONENTS_REGISTER_NODE(SimCameraDecoder)

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SimCameraDecoder>());
    rclcpp::shutdown();
    return 0;
}
