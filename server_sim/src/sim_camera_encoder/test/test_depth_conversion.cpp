// Copyright 2026 k-dev
#include <gtest/gtest.h>
#include <limits>
#include "sim_camera_encoder/depth_conversion.hpp"

TEST(DepthConversion, DefinesInvalidRoundingAndSaturation)
{
  using sim_camera_encoder::metres_to_millimetres;
  EXPECT_EQ(metres_to_millimetres(0.0F), 0U);
  EXPECT_EQ(metres_to_millimetres(-1.0F), 0U);
  EXPECT_EQ(metres_to_millimetres(std::numeric_limits<float>::quiet_NaN()), 0U);
  EXPECT_EQ(metres_to_millimetres(std::numeric_limits<float>::infinity()), 0U);
  EXPECT_EQ(metres_to_millimetres(1.2345F), 1235U);
  EXPECT_EQ(metres_to_millimetres(65.535F), 65535U);
  EXPECT_EQ(metres_to_millimetres(100.0F), 65535U);
}
