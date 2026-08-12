#include "autonomous_racing_core/midpoint_planner.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include "autonomous_racing_msgs/msg/cone_map.hpp"
#include "autonomous_racing_msgs/msg/racing_path.hpp"
#include "rclcpp/rclcpp.hpp"

namespace autonomous_racing_core
{

class RacingPlannerNode final : public rclcpp::Node {
public:
  RacingPlannerNode()
  : Node("racing_planner_node"),
    planner_(declare_parameter("track_width", 6.0),
      declare_parameter("exploration_speed", 2.0))
  {
    path_pub_ = create_publisher<autonomous_racing_msgs::msg::RacingPath>(
      "/racing/local_path", rclcpp::QoS(10));
    map_sub_ = create_subscription<autonomous_racing_msgs::msg::ConeMap>(
      "/racing/cone_map", rclcpp::QoS(10),
      std::bind(&RacingPlannerNode::map_callback, this, std::placeholders::_1));
  }

private:
  void map_callback(const autonomous_racing_msgs::msg::ConeMap::SharedPtr message)
  {
    std::vector<ConePoint> left;
    std::vector<ConePoint> right;
    left.reserve(message->cones.size());
    right.reserve(message->cones.size());
    for (const auto & cone : message->cones) {
      if (cone.state == autonomous_racing_msgs::msg::ConeEstimate::QUARANTINED) {
        continue;
      }
      const auto & position = cone.pose.pose.position;
      if (!std::isfinite(position.x) || !std::isfinite(position.y)) {
        continue;
      }
      const double detector = std::clamp(
        static_cast<double>(cone.detector_score), 0.0, 1.0);
      const double association = std::clamp(
        static_cast<double>(cone.association_confidence), 0.0, 1.0);
      const double depth = std::clamp(
        static_cast<double>(cone.depth_quality), 0.0, 1.0);
      const double pose_quality = std::clamp(
        static_cast<double>(cone.pose_quality), 0.0, 1.0);
      double confidence = std::min({detector, association, depth, pose_quality});
      if (cone.state == autonomous_racing_msgs::msg::ConeEstimate::PROVISIONAL) {
        confidence *= 0.6;
      }
      if (!std::isfinite(confidence) || confidence <= 0.0) {
        continue;
      }
      ConePoint point{position.x, position.y, confidence};
      if (position.y >= 0.0) {
        left.push_back(point);
      } else {
        right.push_back(point);
      }
    }
    const auto stamp = rclcpp::Time(message->header.stamp).seconds();
    const auto candidate = planner_.build(
      left, right, message->header.frame_id, stamp, ++revision_);
    autonomous_racing_msgs::msg::RacingPath output;
    output.header = message->header;
    output.revision = candidate.revision;
    output.mode = autonomous_racing_msgs::msg::RacingPath::ROLLING;
    output.closed_loop = false;
    output.points.reserve(candidate.points.size());
    for (const auto & point : candidate.points) {
      autonomous_racing_msgs::msg::RacingPathPoint msg_point;
      msg_point.pose.position.x = point.x;
      msg_point.pose.position.y = point.y;
      msg_point.pose.orientation.w = 1.0;
      msg_point.target_speed = static_cast<float>(point.target_speed);
      msg_point.confidence = static_cast<float>(point.confidence);
      msg_point.observation_support = msg_point.confidence;
      msg_point.pose_quality = msg_point.confidence;
      msg_point.corridor_geometry = msg_point.confidence;
      msg_point.continuity = msg_point.confidence;
      msg_point.recency = msg_point.confidence;
      msg_point.localization = message->localization_confidence;
      msg_point.state = point.state;
      output.points.push_back(msg_point);
    }
    path_pub_->publish(output);
  }

  MidpointPlanner planner_;
  std::uint64_t revision_{0};
  rclcpp::Publisher<autonomous_racing_msgs::msg::RacingPath>::SharedPtr path_pub_;
  rclcpp::Subscription<autonomous_racing_msgs::msg::ConeMap>::SharedPtr map_sub_;
};

}  // namespace autonomous_racing_core

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<autonomous_racing_core::RacingPlannerNode>());
  rclcpp::shutdown();
  return 0;
}
