// Copyright 2026 k-dev

#include <chrono>
#include <map>
#include <memory>
#include <mutex>
#include <stdexcept>

#include <cv_bridge/cv_bridge.hpp>
#include <gz/msgs/image.pb.h>
#include <gz/transport/Node.hh>
#include <image_transport/image_transport.hpp>
#include <rclcpp/rclcpp.hpp>
#include "sim_camera_encoder/depth_conversion.hpp"
#include "sim_camera_encoder/zstd_depth_encoder.hpp"

class SimCameraEncoder : public rclcpp::Node
{
public:
  SimCameraEncoder()
  : Node("sim_camera_encoder")
  {
    auto qos = rmw_qos_profile_default;
    qos.history = RMW_QOS_POLICY_HISTORY_KEEP_LAST;
    qos.depth = 2;
    qos.reliability = RMW_QOS_POLICY_RELIABILITY_RELIABLE;
    rgb_pub_ = image_transport::create_publisher(this, "~/rgb", qos);
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

private:
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
    rgb_pub_.publish(cv_bridge::CvImage(header, "bgr8", bgr).toImageMsg());
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
  image_transport::Publisher rgb_pub_;
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
