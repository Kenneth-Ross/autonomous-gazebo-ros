#include <gtest/gtest.h>
#include "sim_camera_decoder/latency_stats.hpp"

TEST(LatencyStats, ComputesConservativeNearestRankPercentile)
{
  sim_camera_decoder::LatencyStats stats;
  for (double value : {4.1, 1.0, 3.0, 2.0, 5.0}) {
    stats.add(value);
  }
  EXPECT_DOUBLE_EQ(stats.percentile(0.95), 5.0);
  EXPECT_EQ(stats.size(), 5U);
}

TEST(LatencyStats, RejectsInvalidSamplesClampsAndClears)
{
  sim_camera_decoder::LatencyStats stats(2);
  stats.add(-1.0);
  stats.add(1.0);
  stats.add(3.0);
  EXPECT_EQ(stats.size(), 2U);
  EXPECT_DOUBLE_EQ(stats.percentile(1.0), 2.0);
  stats.clear();
  EXPECT_EQ(stats.size(), 0U);
}
