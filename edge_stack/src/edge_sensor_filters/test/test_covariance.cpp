#include "edge_sensor_filters/covariance.hpp"
#include <gtest/gtest.h>
TEST(Covariance, OdometryMatchesLegacyContract)
{
  nav_msgs::msg::Odometry msg; edge_sensor_filters::inject_covariance(msg);
  EXPECT_DOUBLE_EQ(msg.pose.covariance[0], 0.05); EXPECT_DOUBLE_EQ(msg.pose.covariance[7], 0.05);
    EXPECT_DOUBLE_EQ(msg.pose.covariance[35], 0.1);
  EXPECT_DOUBLE_EQ(msg.twist.covariance[0], 0.02); EXPECT_DOUBLE_EQ(msg.twist.covariance[7], 0.02);
    EXPECT_DOUBLE_EQ(msg.twist.covariance[35], 0.05);
  EXPECT_DOUBLE_EQ(msg.pose.covariance[14], 1e6); EXPECT_DOUBLE_EQ(msg.twist.covariance[21], 1e6);
}
TEST(Covariance, ImuMatchesLegacyContract)
{
  sensor_msgs::msg::Imu msg; edge_sensor_filters::inject_covariance(msg);
  EXPECT_DOUBLE_EQ(msg.orientation_covariance[8], 0.01);
    EXPECT_DOUBLE_EQ(msg.angular_velocity_covariance[8], 0.005);
    EXPECT_DOUBLE_EQ(msg.linear_acceleration_covariance[0], 0.1);
  EXPECT_DOUBLE_EQ(msg.orientation_covariance[0], 1e6);
    EXPECT_DOUBLE_EQ(msg.angular_velocity_covariance[4], 1e6);
    EXPECT_DOUBLE_EQ(msg.linear_acceleration_covariance[8], 1e6);
}
