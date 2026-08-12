#include "autonomous_racing_core/pure_pursuit_controller.hpp"

#include <cmath>
#include <memory>
#include <stdexcept>
#include <string>

#include "autonomous_racing_msgs/msg/control_candidate.hpp"
#include "autonomous_racing_msgs/msg/racing_path.hpp"
#include "nav_msgs/msg/odometry.hpp"
#include "rclcpp/rclcpp.hpp"

namespace autonomous_racing_core
{

class RacingControllerNode final : public rclcpp::Node {
public:
  RacingControllerNode()
  : Node("racing_controller_node")
  {
    PurePursuitController::Config config;
    config.wheelbase = declare_parameter("wheelbase", 1.511);
    config.lookahead = declare_parameter("lookahead_distance", 3.0);
    config.lookahead_gain = declare_parameter("lookahead_gain", 0.5);
    config.min_lookahead = declare_parameter("min_lookahead", 1.5);
    config.max_lookahead = declare_parameter("max_lookahead", 8.0);
    config.max_steering = declare_parameter("max_steering", 0.6108);
    config.freshness_timeout = declare_parameter("path_timeout", 0.2);
    odom_timeout_ = declare_parameter("odom_timeout", 0.2);
    if (!std::isfinite(odom_timeout_) || odom_timeout_ <= 0.0) {
      throw std::invalid_argument("odom_timeout must be finite and positive");
    }
    controller_ = std::make_unique<PurePursuitController>(config);
    path_sub_ = create_subscription<autonomous_racing_msgs::msg::RacingPath>(
      "/racing/local_path", rclcpp::QoS(10),
      std::bind(&RacingControllerNode::path_callback, this, std::placeholders::_1));
    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>(
      "/odometry/filtered", rclcpp::QoS(10),
      std::bind(&RacingControllerNode::odom_callback, this, std::placeholders::_1));
    candidate_pub_ = create_publisher<autonomous_racing_msgs::msg::ControlCandidate>(
      "/racing/control_candidate", rclcpp::QoS(10));
    timer_ = create_wall_timer(
      std::chrono::milliseconds(20),
      std::bind(&RacingControllerNode::publish_candidate, this));
  }

private:
  void path_callback(const autonomous_racing_msgs::msg::RacingPath::SharedPtr message)
  {
    path_.frame_id = message->header.frame_id;
    path_.stamp = rclcpp::Time(message->header.stamp).seconds();
    path_.revision = message->revision;
    path_.mode = message->mode;
    path_.closed_loop = message->closed_loop;
    path_.points.clear();
    path_.points.reserve(message->points.size());
    for (const auto & point : message->points) {
      path_.points.push_back({
          point.pose.position.x, point.pose.position.y,
          point.target_speed, point.confidence, point.state});
    }
  }

  void odom_callback(const nav_msgs::msg::Odometry::SharedPtr message)
  {
    pose_.x = message->pose.pose.position.x;
    pose_.y = message->pose.pose.position.y;
    const auto & q = message->pose.pose.orientation;
    pose_.yaw = std::atan2(2.0 * (q.w * q.z + q.x * q.y),
                           1.0 - 2.0 * (q.y * q.y + q.z * q.z));
    speed_ = message->twist.twist.linear.x;
    odom_received_at_ = get_clock()->now().seconds();
    have_odom_ = true;
  }

  void publish_candidate()
  {
    const double now = get_clock()->now().seconds();
    CommandCandidate command;
    if (!have_odom_) {
      command.fault_reason = "odometry_missing";
    } else if (now - odom_received_at_ > odom_timeout_ ||
      now - odom_received_at_ < -0.05)
    {
      command.fault_reason = "odometry_stale";
    } else {
      command = controller_->compute(path_, pose_, speed_, now);
    }
    autonomous_racing_msgs::msg::ControlCandidate message;
    message.header.stamp = get_clock()->now();
    message.header.frame_id = "base_link";
    message.speed = static_cast<float>(command.speed);
    message.steering = static_cast<float>(command.steering);
    message.path_revision = command.path_revision;
    message.confidence = static_cast<float>(command.confidence);
    message.valid = command.valid;
    message.fault_reason = command.fault_reason;
    candidate_pub_->publish(message);
  }

  std::unique_ptr<PurePursuitController> controller_;
  PathCandidate path_;
  VehiclePose pose_;
  double speed_{0.0};
  double odom_received_at_{0.0};
  double odom_timeout_{0.2};
  bool have_odom_{false};
  rclcpp::Subscription<autonomous_racing_msgs::msg::RacingPath>::SharedPtr path_sub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_;
  rclcpp::Publisher<autonomous_racing_msgs::msg::ControlCandidate>::SharedPtr candidate_pub_;
  rclcpp::TimerBase::SharedPtr timer_;
};

}  // namespace autonomous_racing_core

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  rclcpp::spin(std::make_shared<autonomous_racing_core::RacingControllerNode>());
  rclcpp::shutdown();
  return 0;
}
