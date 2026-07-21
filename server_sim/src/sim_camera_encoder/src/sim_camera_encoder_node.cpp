// Copyright 2026 k-dev

#include <chrono>
#include <functional>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>
#include <string>

#include <cv_bridge/cv_bridge.hpp>
#include <ffmpeg_encoder_decoder/encoder.hpp>
#include <ffmpeg_image_transport_msgs/msg/ffmpeg_packet.hpp>
#include <gz/msgs/image.pb.h>
#include <gz/transport/Node.hh>
#include <rclcpp/rclcpp.hpp>
#include "sim_camera_encoder/depth_conversion.hpp"
#include "sim_camera_encoder/zstd_depth_encoder.hpp"

using FFMPEGPacket = ffmpeg_image_transport_msgs::msg::FFMPEGPacket;

class SimCameraEncoder : public rclcpp::Node
{
public:
  SimCameraEncoder()
  : Node("sim_camera_encoder")
  {
    rgb_pub_ = create_publisher<FFMPEGPacket>(
      "~/rgb/ffmpeg", rclcpp::QoS(rclcpp::KeepLast(2)).reliable());
    const std::string rgb_base = "sim_camera_encoder.rgb.ffmpeg.";
    rgb_encoder_.setEncoder(declare_parameter<std::string>(rgb_base + "encoder", "hevc_nvenc"));
    rgb_encoder_.addAVOption(
      "preset", declare_parameter<std::string>(rgb_base + "preset", "p1"));
    rgb_encoder_.addAVOption("tune", declare_parameter<std::string>(rgb_base + "tune", "ull"));
    rgb_encoder_.setBitRate(declare_parameter<int>(rgb_base + "bit_rate", 20000000));
    rgb_encoder_.setGOPSize(declare_parameter<int>(rgb_base + "gop_size", 10));
    rgb_encoder_.setMaxBFrames(declare_parameter<int>(rgb_base + "max_b_frames", 0));
    rgb_encoder_.setFrameRate(30, 1);
    depth_pub_ = create_publisher<sensor_msgs::msg::CompressedImage>(
      "~/depth/zstd", rclcpp::QoS(rclcpp::KeepLast(2)).reliable());
    zstd_level_ = declare_parameter<int>("depth_zstd_level", 1);
    if (zstd_level_ < 1 || zstd_level_ > ZSTD_maxCLevel()) {
      throw std::invalid_argument("depth_zstd_level outside supported range");
    }
    gz_node_ = std::make_unique<gz::transport::Node>();
    const bool rgb_ok = gz_node_->Subscribe(
      "/oakd/rgbd_camera/image", &SimCameraEncoder::on_rgb, this);
    const bool depth_ok = gz_node_->Subscribe(
      "/oakd/rgbd_camera/depth_image", &SimCameraEncoder::on_depth, this);
    if (!rgb_ok || !depth_ok) {throw std::runtime_error("Gazebo RGB-D subscription failed");}
    timer_ = create_wall_timer(std::chrono::seconds(5), [this]() {report();});
  }

  ~SimCameraEncoder() override
  {
    if (rgb_encoder_.isInitialized()) {rgb_encoder_.flush();}
  }

private:
  void publish_rgb_packet(
    const std::string & frame_id, const rclcpp::Time & stamp, const std::string & encoding,
    uint32_t width, uint32_t height, uint64_t pts, uint8_t flags, uint8_t * data, size_t size)
  {
    FFMPEGPacket packet;
    packet.header.frame_id = frame_id;
    packet.header.stamp = stamp;
    packet.width = width;
    packet.height = height;
    packet.encoding = encoding;
    packet.pts = pts;
    packet.flags = flags;
    packet.is_bigendian = false;
    packet.data.assign(data, data + size);
    rgb_pub_->publish(packet);
  }
  using Queue = std::map<int64_t, gz::msgs::Image>;
  static int64_t stamp(const gz::msgs::Image & msg)
  {
    return msg.header().stamp().sec() * 1000000000LL + msg.header().stamp().nsec();
  }
  static void trim(Queue & queue, uint64_t & drops)
  {
    while (queue.size() > 2U) {queue.erase(queue.begin()); ++drops;}
  }
  void on_rgb(const gz::msgs::Image & msg)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    ++rgb_received_; rgb_[stamp(msg)] = msg; trim(rgb_, rgb_dropped_); publish_pair();
  }
  void on_depth(const gz::msgs::Image & msg)
  {
    std::lock_guard<std::mutex> lock(mutex_);
    ++depth_received_; depth_[stamp(msg)] = msg; trim(depth_, depth_dropped_); publish_pair();
  }
  void publish_pair()
  {
    auto rgb_it = rgb_.end();
    auto depth_it = depth_.end();
    for (auto it = rgb_.begin(); it != rgb_.end(); ++it) {
      auto candidate = depth_.find(it->first);
      if (candidate != depth_.end()) {rgb_it = it; depth_it = candidate;}
    }
    if (rgb_it == rgb_.end()) {return;}
    const auto & rgb = rgb_it->second;
    const auto & depth = depth_it->second;
    const size_t count = static_cast<size_t>(rgb.width()) * rgb.height();
    if (rgb.width() != depth.width() || rgb.height() != depth.height() ||
      rgb.data().size() < count * 3U || depth.data().size() < count * sizeof(float))
    {
      ++malformed_; rgb_.erase(rgb_.begin(), std::next(rgb_it));
      depth_.erase(depth_.begin(), std::next(depth_it)); return;
    }
    std_msgs::msg::Header header;
    header.stamp.sec = rgb.header().stamp().sec();
    header.stamp.nanosec = rgb.header().stamp().nsec();
    header.frame_id = "camera_link_optical";
    cv::Mat rgb_view(rgb.height(), rgb.width(), CV_8UC3, const_cast<char *>(rgb.data().data()));
    cv::Mat bgr;
    cv::cvtColor(rgb_view, bgr, cv::COLOR_RGB2BGR);
    cv::Mat depth_mm(depth.height(), depth.width(), CV_16UC1);
    const auto * input = reinterpret_cast<const float *>(depth.data().data());
    auto * output = depth_mm.ptr<uint16_t>();
    for (size_t i = 0; i < count; ++i) {
      output[i] = sim_camera_encoder::metres_to_millimetres(input[i]);
    }
    auto rgb_image = cv_bridge::CvImage(header, "bgr8", bgr).toImageMsg();
    if (!rgb_encoder_.isInitialized()) {
      const auto callback = std::bind(
        &SimCameraEncoder::publish_rgb_packet, this, std::placeholders::_1,
        std::placeholders::_2, std::placeholders::_3, std::placeholders::_4,
        std::placeholders::_5, std::placeholders::_6, std::placeholders::_7,
        std::placeholders::_8, std::placeholders::_9);
      if (!rgb_encoder_.initialize(rgb_image->width, rgb_image->height, callback,
        rgb_image->encoding))
      {
        throw std::runtime_error("RGB encoder initialization failed");
      }
    }
    rgb_encoder_.encodeImage(*rgb_image);
    auto depth_image = cv_bridge::CvImage(header, "16UC1", depth_mm).toImageMsg();
    depth_pub_->publish(sim_camera_encoder::encode_zstd_image(*depth_image, zstd_level_));
    ++published_;
    rgb_.erase(rgb_.begin(), std::next(rgb_it));
    depth_.erase(depth_.begin(), std::next(depth_it));
  }
  void report()
  {
    std::lock_guard<std::mutex> lock(mutex_);
    RCLCPP_INFO(get_logger(),
      "rgb_received=%lu depth_received=%lu pairs_published=%lu rgb_dropped=%lu "
      "depth_dropped=%lu malformed=%lu rgb_queue=%zu depth_queue=%zu",
      rgb_received_, depth_received_, published_, rgb_dropped_, depth_dropped_, malformed_,
      rgb_.size(), depth_.size());
  }
  rclcpp::Publisher<FFMPEGPacket>::SharedPtr rgb_pub_;
  ffmpeg_encoder_decoder::Encoder rgb_encoder_;
  rclcpp::Publisher<sensor_msgs::msg::CompressedImage>::SharedPtr depth_pub_;
  std::unique_ptr<gz::transport::Node> gz_node_;
  Queue rgb_, depth_;
  std::mutex mutex_;
  rclcpp::TimerBase::SharedPtr timer_;
  int zstd_level_{1};
  uint64_t rgb_received_{0}, depth_received_{0}, published_{0};
  uint64_t rgb_dropped_{0}, depth_dropped_{0}, malformed_{0};
};

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<SimCameraEncoder>());
  rclcpp::shutdown();
  return 0;
}
