#pragma once
#include <array>
#include <cstddef>
#include <nav_msgs/msg/odometry.hpp>
#include <sensor_msgs/msg/imu.hpp>
namespace edge_sensor_filters
{
inline void inject_covariance(nav_msgs::msg::Odometry & msg)
{
  msg.pose.covariance.fill(0.0); msg.twist.covariance.fill(0.0);
  constexpr std::array<std::size_t, 6> diagonal{0, 7, 14, 21, 28, 35};
  for (const auto index : diagonal) {
    msg.pose.covariance[index] = 1e6; msg.twist.covariance[index] = 1e6;
  }
  msg.pose.covariance[0] = 0.05; msg.pose.covariance[7] = 0.05; msg.pose.covariance[35] = 0.1;
  msg.twist.covariance[0] = 0.02; msg.twist.covariance[7] = 0.02; msg.twist.covariance[35] = 0.05;
}
inline void inject_covariance(sensor_msgs::msg::Imu & msg)
{
  msg.orientation_covariance.fill(0.0); msg.angular_velocity_covariance.fill(0.0);
  msg.linear_acceleration_covariance.fill(0.0);
  constexpr std::array<std::size_t, 3> diagonal{0, 4, 8};
  for (const auto index : diagonal) {
    msg.orientation_covariance[index] = 1e6; msg.angular_velocity_covariance[index] = 1e6;
    msg.linear_acceleration_covariance[index] = 1e6;
  }
  msg.orientation_covariance[8] = 0.01; msg.angular_velocity_covariance[8] = 0.005;
  msg.linear_acceleration_covariance[0] = 0.1;
}
}  // namespace edge_sensor_filters
