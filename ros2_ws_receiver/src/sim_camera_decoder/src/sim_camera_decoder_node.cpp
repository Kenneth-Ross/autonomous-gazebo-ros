#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "image_transport/image_transport.hpp"

class SimCameraDecoder : public rclcpp::Node {
public:
    SimCameraDecoder() : Node("ffmpeg_decoder") {
        // Output publisher (uncompressed raw image)
        pub_ = image_transport::create_publisher(this, "~/super_frame_local", rmw_qos_profile_default);
        
        // Input subscriber (requesting 'ffmpeg' transport from the base topic)
        sub_ = image_transport::create_subscription(this, "/oakd/super_frame/image_raw", 
            [this](const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
                RCLCPP_INFO_ONCE(this->get_logger(), "Received first decoded frame from ffmpeg!");
                pub_.publish(msg);
            },
            "ffmpeg", rmw_qos_profile_default);
            
        RCLCPP_INFO(this->get_logger(), "Custom FFMPEG Decoder Node Started.");
    }
private:
    image_transport::Publisher pub_;
    image_transport::Subscriber sub_;
};

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SimCameraDecoder>());
    rclcpp::shutdown();
    return 0;
}
