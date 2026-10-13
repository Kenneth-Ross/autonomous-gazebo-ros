#include "autonomous_racing_core/safety_supervisor.hpp"

#include <chrono>
#include <cstddef>
#include <memory>
#include <string>

#include "autonomous_racing_msgs/msg/control_candidate.hpp"
#include "autonomous_racing_msgs/msg/recorder_heartbeat.hpp"
#include "autonomous_racing_msgs/msg/supervisor_status.hpp"
#include "autonomous_racing_msgs/srv/abort_run.hpp"
#include "autonomous_racing_msgs/srv/prepare_run.hpp"
#include "autonomous_racing_msgs/srv/start_run.hpp"
#include "autonomous_racing_core/types.hpp"
#include "geometry_msgs/msg/twist_stamped.hpp"
#include "rclcpp/rclcpp.hpp"

namespace autonomous_racing_core
{

class RacingSupervisorNode final : public rclcpp::Node {
public:
  RacingSupervisorNode()
  : Node("racing_supervisor_node")
  {
    SafetySupervisor::Config config;
    config.command_timeout = declare_parameter("command_timeout", 0.2);
    config.recorder_timeout = declare_parameter("recorder_timeout", 0.5);
    command_timeout_ = config.command_timeout;
    config.max_speed = declare_parameter("max_speed", 5.0);
    config.max_steering = declare_parameter("max_steering", 0.6108);
    config.require_recorder = declare_parameter("require_recorder_heartbeat", true);
    supervisor_ = std::make_unique<SafetySupervisor>(config);
    run_id_ = declare_parameter("run_id", "");
    control_group_ = create_callback_group(rclcpp::CallbackGroupType::MutuallyExclusive);
    rclcpp::SubscriptionOptions callback_options;
    callback_options.callback_group = control_group_;
    candidate_sub_ = create_subscription<autonomous_racing_msgs::msg::ControlCandidate>(
      "/racing/control_candidate", rclcpp::QoS(10),
      std::bind(&RacingSupervisorNode::candidate_callback, this, std::placeholders::_1),
      callback_options);
    recorder_sub_ = create_subscription<autonomous_racing_msgs::msg::RecorderHeartbeat>(
      "/racing/recorder/heartbeat", rclcpp::QoS(10),
      std::bind(&RacingSupervisorNode::recorder_callback, this, std::placeholders::_1),
      callback_options);
    command_pub_ = create_publisher<geometry_msgs::msg::TwistStamped>(
      "/car/control_request", rclcpp::QoS(10));
    status_pub_ = create_publisher<autonomous_racing_msgs::msg::SupervisorStatus>(
      "/racing/supervisor_status", rclcpp::QoS(10));
    prepare_srv_ = create_service<autonomous_racing_msgs::srv::PrepareRun>(
      "/racing/prepare", std::bind(&RacingSupervisorNode::prepare_callback, this,
      std::placeholders::_1, std::placeholders::_2), rclcpp::ServicesQoS(), control_group_);
    start_srv_ = create_service<autonomous_racing_msgs::srv::StartRun>(
      "/racing/start", std::bind(&RacingSupervisorNode::start_callback, this,
      std::placeholders::_1, std::placeholders::_2), rclcpp::ServicesQoS(), control_group_);
    abort_srv_ = create_service<autonomous_racing_msgs::srv::AbortRun>(
      "/racing/abort", std::bind(&RacingSupervisorNode::abort_callback, this,
      std::placeholders::_1, std::placeholders::_2), rclcpp::ServicesQoS(), control_group_);
    timer_ = create_wall_timer(
      std::chrono::milliseconds(20),
      std::bind(&RacingSupervisorNode::publish_outputs, this), control_group_);
    RCLCPP_INFO(get_logger(), "racing supervisor ready");
  }

private:
  double now() const {return get_clock()->now().seconds();}

  void candidate_callback(
    const autonomous_racing_msgs::msg::ControlCandidate::SharedPtr message)
  {
    const auto stamp = rclcpp::Time(message->header.stamp).seconds();
    if (!is_fresh_message_stamp(stamp, now(), command_timeout_)) {
      if (supervisor_->state() == SupervisorState::RACING) {
        supervisor_->abort("candidate_stale");
      }
      return;
    }
    CommandCandidate candidate;
    candidate.speed = message->speed;
    candidate.steering = message->steering;
    candidate.confidence = message->confidence;
    candidate.path_revision = message->path_revision;
    candidate.valid = message->valid;
    candidate.fault_reason = message->fault_reason;
    supervisor_->accept_candidate(candidate, now(), stamp);
  }

  void recorder_callback(
    const autonomous_racing_msgs::msg::RecorderHeartbeat::SharedPtr message)
  {
    const bool healthy = message->bag_healthy &&
      (message->state == autonomous_racing_msgs::msg::RecorderHeartbeat::READY ||
      message->state == autonomous_racing_msgs::msg::RecorderHeartbeat::RECORDING);
    const auto stamp = rclcpp::Time(message->header.stamp).seconds();
    supervisor_->update_recorder(now(), message->run_id, healthy, stamp);
  }

  void prepare_callback(
    const std::shared_ptr<autonomous_racing_msgs::srv::PrepareRun::Request> request,
    std::shared_ptr<autonomous_racing_msgs::srv::PrepareRun::Response> response)
  {
    RCLCPP_INFO(get_logger(), "prepare callback entered");
    run_id_ = request->run_id_hint;
    supervisor_->prepare(run_id_);
    response->success = true;
    response->run_id = run_id_;
    response->message =
      "run prepared; prepare recorder separately, then explicit start required";
    RCLCPP_INFO(get_logger(), "prepare callback completed");
  }

  void start_callback(
    const std::shared_ptr<autonomous_racing_msgs::srv::StartRun::Request> request,
    std::shared_ptr<autonomous_racing_msgs::srv::StartRun::Response> response)
  {
    if (request->start) {
      response->success = supervisor_->start(now());
      response->message = response->success ?
        "run started" : "run not ready or recorder heartbeat missing";
    } else {
      supervisor_->abort("operator_stop");
      response->success = true;
      response->message = "run stopped";
    }
  }

  void abort_callback(
    const std::shared_ptr<autonomous_racing_msgs::srv::AbortRun::Request> request,
    std::shared_ptr<autonomous_racing_msgs::srv::AbortRun::Response> response)
  {
    const auto reason = request->reason.empty() ? "operator_abort" : request->reason;
    supervisor_->abort(reason);
    response->success = true;
    response->message = supervisor_->stop_reason();
  }

  static std::uint8_t state_value(SupervisorState state)
  {
    return static_cast<std::uint8_t>(state);
  }

  void publish_outputs()
  {
    ++publish_count_;
    if (publish_count_ == 1U) {
      RCLCPP_INFO(get_logger(), "supervisor timer active");
    }
    const auto output = supervisor_->tick(now());
    const auto stamp = get_clock()->now();
    geometry_msgs::msg::TwistStamped command;
    command.header.stamp = stamp;
    command.header.frame_id = "base_link";
    command.twist.linear.x = output.speed;
    command.twist.angular.z = output.steering;
    command_pub_->publish(command);

    autonomous_racing_msgs::msg::SupervisorStatus status;
    status.header.stamp = stamp;
    status.run_id = supervisor_->run_id();
    status.state = state_value(output.state);
    status.stop_reason = output.reason;
    status.controller_ready = output.reason.empty();
    status.planner_ready = status.controller_ready;
    status.recorder_ready = supervisor_->recorder_ready(now());
    status_pub_->publish(status);
  }


  std::unique_ptr<SafetySupervisor> supervisor_;
  std::string run_id_;
  double command_timeout_{0.2};
  rclcpp::Subscription<autonomous_racing_msgs::msg::ControlCandidate>::SharedPtr candidate_sub_;
  rclcpp::Subscription<autonomous_racing_msgs::msg::RecorderHeartbeat>::SharedPtr recorder_sub_;
  rclcpp::Publisher<geometry_msgs::msg::TwistStamped>::SharedPtr command_pub_;
  rclcpp::Publisher<autonomous_racing_msgs::msg::SupervisorStatus>::SharedPtr status_pub_;
  rclcpp::Service<autonomous_racing_msgs::srv::PrepareRun>::SharedPtr prepare_srv_;
  rclcpp::Service<autonomous_racing_msgs::srv::StartRun>::SharedPtr start_srv_;
  rclcpp::Service<autonomous_racing_msgs::srv::AbortRun>::SharedPtr abort_srv_;
  rclcpp::CallbackGroup::SharedPtr control_group_;
  rclcpp::TimerBase::SharedPtr timer_;
  std::size_t publish_count_{0};
};

}  // namespace autonomous_racing_core

int main(int argc, char **argv)
{
  rclcpp::init(argc, argv);
  auto node = std::make_shared<autonomous_racing_core::RacingSupervisorNode>();
  rclcpp::executors::MultiThreadedExecutor executor(rclcpp::ExecutorOptions(), 4);
  executor.add_node(node);
  executor.spin();
  rclcpp::shutdown();
  return 0;
}
