#include "autonomous_racing_core/midpoint_planner.hpp"

#include <algorithm>
#include <cmath>
#include <memory>
#include <string>
#include <vector>

#include "autonomous_racing_core/types.hpp"
#include "autonomous_racing_msgs/msg/cone_map.hpp"
#include "autonomous_racing_msgs/msg/racing_path.hpp"
#include "geometry_msgs/msg/point_stamped.hpp"
#include "rclcpp/rclcpp.hpp"
#include "tf2/exceptions.h"
#include "tf2_geometry_msgs/tf2_geometry_msgs.hpp"
#include "tf2_ros/buffer.h"
#include "tf2_ros/transform_listener.h"

namespace autonomous_racing_core
{

class RacingPlannerNode final : public rclcpp::Node {
public:
  RacingPlannerNode()
  : Node("racing_planner_node"),
    planner_(declare_parameter("track_width", 6.0),
      declare_parameter("exploration_speed", 2.0)),
    target_frame_(declare_parameter("vehicle_frame", "base_link")),
    input_timeout_(declare_parameter("input_timeout", 0.5)),
    tf_buffer_(get_clock()),
    tf_listener_(tf_buffer_)
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
    const double stamp = rclcpp::Time(message->header.stamp).seconds();
    if (message->header.frame_id.empty() || target_frame_.empty() ||
      !std::isfinite(message->localization_confidence) ||
      message->localization_confidence <= 0.0F ||
      message->localization_confidence > 1.0F ||
      !is_fresh_message_stamp(stamp, get_clock()->now().seconds(), input_timeout_))
    {
      publish_empty_path(*message);
      return;
    }

    geometry_msgs::msg::TransformStamped map_to_vehicle;
    geometry_msgs::msg::TransformStamped vehicle_to_map;
    try {
      const auto time = rclcpp::Time(message->header.stamp);
      map_to_vehicle = tf_buffer_.lookupTransform(
        target_frame_, message->header.frame_id, time);
      vehicle_to_map = tf_buffer_.lookupTransform(
        message->header.frame_id, target_frame_, time);
    } catch (const tf2::TransformException & error) {
      RCLCPP_WARN_THROTTLE(
        get_logger(), *get_clock(), 2000, "cone map transform unavailable: %s", error.what());
      publish_empty_path(*message);
      return;
    }

    std::vector<ConePoint> left;
    std::vector<ConePoint> right;
    left.reserve(message->cones.size());
    right.reserve(message->cones.size());
    for (const auto & cone : message->cones) {
      if (cone.state == autonomous_racing_msgs::msg::ConeEstimate::QUARANTINED) {
        continue;
      }
      if (!std::isfinite(cone.pose.pose.position.x) ||
        !std::isfinite(cone.pose.pose.position.y))
      {
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
      geometry_msgs::msg::PointStamped map_point;
      map_point.header = message->header;
      map_point.point = cone.pose.pose.position;
      geometry_msgs::msg::PointStamped vehicle_point;
      tf2::doTransform(map_point, vehicle_point, map_to_vehicle);
      const auto & position = vehicle_point.point;
      const double observed_at = rclcpp::Time(cone.last_observed).seconds();
      if (!std::isfinite(position.x) || !std::isfinite(position.y) ||
        !std::isfinite(position.z) ||
        !is_fresh_message_stamp(observed_at, get_clock()->now().seconds(), input_timeout_))
      {
        continue;
      }
      confidence *= static_cast<double>(message->localization_confidence);
      ConePoint point{position.x, position.y, confidence};
      if (position.y >= 0.0) {
        left.push_back(point);
      } else {
        right.push_back(point);
      }
    }
    const auto candidate = planner_.build(
      left, right, message->header.frame_id, stamp, ++revision_);
    autonomous_racing_msgs::msg::RacingPath output;
    output.header = message->header;
    output.revision = candidate.revision;
    output.mode = autonomous_racing_msgs::msg::RacingPath::ROLLING;
    output.closed_loop = false;
    output.points.reserve(candidate.points.size());
    for (const auto & point : candidate.points) {
      geometry_msgs::msg::PointStamped vehicle_point;
      vehicle_point.header.frame_id = target_frame_;
      vehicle_point.header.stamp = message->header.stamp;
      vehicle_point.point.x = point.x;
      vehicle_point.point.y = point.y;
      geometry_msgs::msg::PointStamped map_point;
      tf2::doTransform(vehicle_point, map_point, vehicle_to_map);
      if (!std::isfinite(map_point.point.x) || !std::isfinite(map_point.point.y) ||
        !std::isfinite(map_point.point.z))
      {
        continue;
      }
      autonomous_racing_msgs::msg::RacingPathPoint msg_point;
      msg_point.pose.position.x = map_point.point.x;
      msg_point.pose.position.y = map_point.point.y;
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

  void publish_empty_path(const autonomous_racing_msgs::msg::ConeMap & message)
  {
    autonomous_racing_msgs::msg::RacingPath output;
    output.header = message.header;
    output.revision = ++revision_;
    output.mode = autonomous_racing_msgs::msg::RacingPath::ROLLING;
    output.closed_loop = false;
    path_pub_->publish(output);
  }

  MidpointPlanner planner_;
  std::string target_frame_;
  double input_timeout_;
  tf2_ros::Buffer tf_buffer_;
  tf2_ros::TransformListener tf_listener_;
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
