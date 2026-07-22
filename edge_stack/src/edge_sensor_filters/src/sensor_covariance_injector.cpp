#include "edge_sensor_filters/covariance.hpp"
#include <atomic>
#include <chrono>
#include <cstdint>
#include <memory>
#include <utility>
#include <nav_msgs/msg/odometry.hpp>
#include <rclcpp/rclcpp.hpp>
#include <rclcpp_components/register_node_macro.hpp>
#include <sensor_msgs/msg/imu.hpp>
namespace edge_sensor_filters
{
class SensorCovarianceInjector : public rclcpp::Node
{
public:
  explicit SensorCovarianceInjector(const rclcpp::NodeOptions & options)
  : Node("sensor_covariance_injector", options)
  {
    const auto qos = rclcpp::SensorDataQoS();
    odom_pub_ = create_publisher<nav_msgs::msg::Odometry>("/odom/filtered_input", qos);
    imu_pub_ = create_publisher<sensor_msgs::msg::Imu>("/imu/filtered_input", qos);
    odom_sub_ = create_subscription<nav_msgs::msg::Odometry>("/odom", qos,
        [this](nav_msgs::msg::Odometry::UniquePtr msg) {
          inject_covariance(*msg); odom_pub_->publish(std::move(msg)); ++odom_count_;
                                                                                                                                   });
    imu_sub_ = create_subscription<sensor_msgs::msg::Imu>("/imu", qos,
        [this](sensor_msgs::msg::Imu::UniquePtr msg) {
          inject_covariance(*msg); imu_pub_->publish(std::move(msg)); ++imu_count_;
                                                                                                                               });
    metrics_timer_ = create_wall_timer(std::chrono::seconds(5), [this]() {
          const auto odom = odom_count_.exchange(0); const auto imu = imu_count_.exchange(0);
          RCLCPP_INFO(get_logger(), "Sensor covariance: odom_rate=%.1f imu_rate=%.1f",
          static_cast<double>(odom) / 5.0, static_cast<double>(imu) / 5.0);
    });
  }

private:
  std::atomic<std::uint64_t> odom_count_{0}; std::atomic<std::uint64_t> imu_count_{0};
  rclcpp::Publisher<nav_msgs::msg::Odometry>::SharedPtr odom_pub_; rclcpp::Publisher<sensor_msgs::msg::Imu>::SharedPtr imu_pub_;
  rclcpp::Subscription<nav_msgs::msg::Odometry>::SharedPtr odom_sub_; rclcpp::Subscription<sensor_msgs::msg::Imu>::SharedPtr imu_sub_;
  rclcpp::TimerBase::SharedPtr metrics_timer_;
};
}  // namespace edge_sensor_filters
RCLCPP_COMPONENTS_REGISTER_NODE(edge_sensor_filters::SensorCovarianceInjector)
