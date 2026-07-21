#include "rclcpp/rclcpp.hpp"
#include "sensor_msgs/msg/image.hpp"
#include "sensor_msgs/msg/camera_info.hpp"
#include "image_transport/image_transport.hpp"
#include "cv_bridge/cv_bridge.hpp"
#include <opencv2/opencv.hpp>
#include "sensor_msgs/msg/compressed_image.hpp"
#include <algorithm>
#include <condition_variable>
#include <mutex>
#include <optional>
#include <stdexcept>
#include <thread>

#include "rclcpp_components/register_node_macro.hpp"

class SimCameraDecoder : public rclcpp::Node {
public:
    SimCameraDecoder(const rclcpp::NodeOptions & options = rclcpp::NodeOptions()) 
    : Node("ffmpeg_decoder", options), last_published_time_(0, 0, this->get_clock()->get_clock_type()) {
        image_width_ = this->declare_parameter<int>("image_width", 1280);
        image_height_ = this->declare_parameter<int>("image_height", 800);
        output_rate_hz_ = this->declare_parameter<double>("output_rate_hz", 5.0);
        frame_id_ = this->declare_parameter<std::string>("frame_id", "camera_link_optical");
        const double fx = this->declare_parameter<double>("camera.fx", 800.0);
        const double fy = this->declare_parameter<double>("camera.fy", 800.0);
        const double cx = this->declare_parameter<double>("camera.cx", image_width_ / 2.0);
        const double cy = this->declare_parameter<double>("camera.cy", image_height_ / 2.0);
        publish_compressed_ = this->declare_parameter<bool>("publish_compressed", true);
        jpeg_quality_ = static_cast<int>(std::clamp<int64_t>(
            this->declare_parameter<int>("jpeg_quality", 50), 0, 100));
        png_compression_ = static_cast<int>(std::clamp<int64_t>(
            this->declare_parameter<int>("png_compression", 3), 0, 9));
        if (image_width_ <= 0 || image_height_ <= 0 || output_rate_hz_ < 0.0) {
            throw std::invalid_argument("dimensions must be positive and output_rate_hz non-negative");
        }
        rgb_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/rgb/image_raw", rclcpp::QoS(10));
        rgb_compressed_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>("/edge/camera/rgb/image_raw/compressed", rclcpp::QoS(10));
        rgb_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/rgb/camera_info", rclcpp::QoS(10));
        depth_pub_ = this->create_publisher<sensor_msgs::msg::Image>("/edge/camera/depth/image_raw", rclcpp::QoS(10));
        depth_compressed_pub_ = this->create_publisher<sensor_msgs::msg::CompressedImage>("/edge/camera/depth/image_raw/compressed", rclcpp::QoS(10));
        depth_info_pub_ = this->create_publisher<sensor_msgs::msg::CameraInfo>("/edge/camera/depth/camera_info", rclcpp::QoS(10));
        
        // Static Camera Info
        static_info_.width = image_width_;
        static_info_.height = image_height_;
        static_info_.k = {fx, 0.0, cx, 0.0, fy, cy, 0.0, 0.0, 1.0};
        static_info_.p = {fx, 0.0, cx, 0.0, 0.0, fy, cy, 0.0, 0.0, 0.0, 1.0, 0.0};
        static_info_.r = {1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0};
        static_info_.distortion_model = "plumb_bob";
        static_info_.d = {0.0, 0.0, 0.0, 0.0, 0.0};

        // Input subscriber
        sub_ = image_transport::create_subscription(this, "/oakd/super_frame/image_raw", 
            std::bind(&SimCameraDecoder::imageCallback, this, std::placeholders::_1),
            "ffmpeg", rmw_qos_profile_default);
            
        if (publish_compressed_) {
            compression_thread_ = std::thread(&SimCameraDecoder::compressionWorker, this);
        }
        RCLCPP_INFO(this->get_logger(), "Decoder started: %dx%d at %.2f Hz%s",
            image_width_, image_height_, output_rate_hz_,
            publish_compressed_ ? ", compressed output enabled" : "");
    }

    ~SimCameraDecoder() override {
        {
            std::lock_guard<std::mutex> lock(compression_mutex_);
            stop_compression_ = true;
            pending_compression_.reset();
        }
        compression_cv_.notify_one();
        if (compression_thread_.joinable()) compression_thread_.join();
    }
private:
    struct CompressionJob {
        std_msgs::msg::Header header;
        cv::Mat rgb;
        cv::Mat depth;
    };

    void imageCallback(const sensor_msgs::msg::Image::ConstSharedPtr & msg) {
        // output_rate_hz == 0 disables throttling.
        rclcpp::Time current_time(msg->header.stamp);
        if (current_time.seconds() == 0.0) {
             current_time = this->now();
        }
        
        const double minimum_period = output_rate_hz_ > 0.0 ? 1.0 / output_rate_hz_ : 0.0;
        if (minimum_period > 0.0 && last_published_time_.nanoseconds() != 0 &&
            current_time > last_published_time_ &&
            (current_time - last_published_time_).seconds() < minimum_period) {
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
        const int width = image_width_;
        if (combined_frame.cols != width * 3 || combined_frame.rows != image_height_) {
            RCLCPP_ERROR_THROTTLE(this->get_logger(), *this->get_clock(), 5000,
                "Unexpected super-frame: got %dx%d, expected %dx%d",
                combined_frame.cols, combined_frame.rows, width * 3, image_height_);
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
        header.frame_id = frame_id_;

        auto rgb_msg = std::make_unique<sensor_msgs::msg::Image>();
        cv_bridge::CvImage(header, "bgr8", rgb_frame).toImageMsg(*rgb_msg);
        auto depth_msg = std::make_unique<sensor_msgs::msg::Image>();
        cv_bridge::CvImage(header, "16UC1", depth_16bit).toImageMsg(*depth_msg);

        static_info_.header = header;

        rgb_pub_->publish(std::move(rgb_msg));
        depth_pub_->publish(std::move(depth_msg));
        
        if (publish_compressed_) {
            {
                std::lock_guard<std::mutex> lock(compression_mutex_);
                pending_compression_ = CompressionJob{header, rgb_frame.clone(), depth_16bit.clone()};
            }
            compression_cv_.notify_one();
        }

        auto info_msg1 = std::make_unique<sensor_msgs::msg::CameraInfo>(static_info_);
        rgb_info_pub_->publish(std::move(info_msg1));
        
        auto info_msg2 = std::make_unique<sensor_msgs::msg::CameraInfo>(static_info_);
        depth_info_pub_->publish(std::move(info_msg2));
    }

    void compressionWorker() {
        while (true) {
            CompressionJob job;
            {
                std::unique_lock<std::mutex> lock(compression_mutex_);
                compression_cv_.wait(lock, [this] {
                    return stop_compression_ || pending_compression_.has_value();
                });
                if (stop_compression_) return;
                job = std::move(*pending_compression_);
                pending_compression_.reset();
            }
            auto rgb_msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
            rgb_msg->header = job.header;
            rgb_msg->format = "jpeg";
            cv::imencode(".jpg", job.rgb, rgb_msg->data, {cv::IMWRITE_JPEG_QUALITY, jpeg_quality_});
            rgb_compressed_pub_->publish(std::move(rgb_msg));

            auto depth_msg = std::make_unique<sensor_msgs::msg::CompressedImage>();
            depth_msg->header = job.header;
            depth_msg->format = "png";
            cv::imencode(".png", job.depth, depth_msg->data, {cv::IMWRITE_PNG_COMPRESSION, png_compression_});
            depth_compressed_pub_->publish(std::move(depth_msg));
        }
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
    int image_width_;
    int image_height_;
    double output_rate_hz_;
    std::string frame_id_;
    bool publish_compressed_;
    int jpeg_quality_;
    int png_compression_;
    std::mutex compression_mutex_;
    std::condition_variable compression_cv_;
    std::optional<CompressionJob> pending_compression_;
    bool stop_compression_{false};
    std::thread compression_thread_;
};

RCLCPP_COMPONENTS_REGISTER_NODE(SimCameraDecoder)

int main(int argc, char **argv) {
    rclcpp::init(argc, argv);
    rclcpp::spin(std::make_shared<SimCameraDecoder>());
    rclcpp::shutdown();
    return 0;
}
