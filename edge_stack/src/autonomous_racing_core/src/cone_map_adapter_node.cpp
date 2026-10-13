#include <algorithm>
#include <cstdint>
#include <cmath>
#include <memory>
#include <string>

#include "autonomous_racing_msgs/msg/cone_estimate.hpp"
#include "autonomous_racing_msgs/msg/cone_map.hpp"
#include "rclcpp/rclcpp.hpp"
#include "visualization_msgs/msg/marker_array.hpp"

namespace autonomous_racing_core
{

class ConeMapAdapterNode final : public rclcpp::Node {
public:
  ConeMapAdapterNode()
  : Node("cone_map_adapter_node")
  {
    map_pub_ = create_publisher<autonomous_racing_msgs::msg::ConeMap>(
      "/racing/cone_map", rclcpp::QoS(10));
    marker_sub_ = create_subscription<visualization_msgs::msg::MarkerArray>(
      "/rtabmap/landmarks", rclcpp::QoS(10),
      std::bind(&ConeMapAdapterNode::marker_callback, this, std::placeholders::_1));
  }

private:
  void marker_callback(
    const visualization_msgs::msg::MarkerArray::SharedPtr message)
  {
    autonomous_racing_msgs::msg::ConeMap output;
    output.map_revision = ++revision_;
    // MarkerArray has no measured observation-quality fields. Keep that
    // uncertainty visible instead of promoting marker presence to confidence.
    output.localization_confidence = 0.0F;
    for (const auto & marker : message->markers) {
      if (marker.action == visualization_msgs::msg::Marker::DELETE ||
        marker.action == visualization_msgs::msg::Marker::DELETEALL ||
        marker.id < 0)
      {
        // Negative or delete IDs cannot prove stable landmark identity.
        continue;
      }
      if (!std::isfinite(marker.pose.position.x) ||
        !std::isfinite(marker.pose.position.y) ||
        !std::isfinite(marker.pose.position.z))
      {
        continue;
      }
      if (output.header.frame_id.empty()) {
        output.header.frame_id = marker.header.frame_id;
        output.header.stamp = marker.header.stamp;
      }
      if (marker.header.frame_id != output.header.frame_id) {
        continue;
      }
      autonomous_racing_msgs::msg::ConeEstimate cone;
      cone.id = static_cast<std::uint64_t>(marker.id);
      cone.pose.pose = marker.pose;
      cone.pose.covariance[0] = 1.0e6;
      cone.pose.covariance[7] = 1.0e6;
      cone.pose.covariance[35] = 1.0e6;
      cone.detector_score = 0.0F;
      cone.observation_count = 1U;
      cone.distinct_view_count = 1U;
      cone.last_observed = marker.header.stamp;
      cone.depth_quality = 0.0F;
      cone.pose_quality = 0.0F;
      cone.association_confidence = 0.0F;
      cone.state = autonomous_racing_msgs::msg::ConeEstimate::QUARANTINED;
      output.cones.push_back(cone);
    }
    map_pub_->publish(output);
  }

  std::uint64_t revision_{0};
  rclcpp::Publisher<autonomous_racing_msgs::msg::ConeMap>::SharedPtr map_pub_;
  rclcpp::Subscription<visualization_msgs::msg::MarkerArray>::SharedPtr marker_sub_;
};

}  // namespace autonomous_racing_core

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<autonomous_racing_core::ConeMapAdapterNode>());
  rclcpp::shutdown();
  return 0;
}
