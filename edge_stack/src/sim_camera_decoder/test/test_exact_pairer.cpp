#include <gtest/gtest.h>
#include "sim_camera_decoder/exact_pairer.hpp"

TEST(ExactPairer, MatchesOnlyExactTimestampsAndSelectsNewest)
{
  sim_camera_decoder::ExactPairer<int, int> pairer(2);
  pairer.push_left(10, 1);
  pairer.push_right(11, 2);
  EXPECT_FALSE(pairer.take_newest_complete());
  pairer.push_left(11, 3);
  pairer.push_right(12, 4);
  pairer.push_left(12, 5);
  auto pair = pairer.take_newest_complete();
  ASSERT_TRUE(pair);
  EXPECT_EQ(pair->first, 5);
  EXPECT_EQ(pair->second, 4);
}

TEST(ExactPairer, DelayedMateSurvivesUntilBoundedCapacityEviction)
{
  sim_camera_decoder::ExactPairer<int, int> pairer(8);
  pairer.push_right(100, 7);
  for (int64_t stamp = 101; stamp <= 107; ++stamp) {
    pairer.push_right(stamp, static_cast<int>(stamp));
  }
  EXPECT_FALSE(pairer.take_newest_complete());
  pairer.push_left(100, 8);
  auto pair = pairer.take_newest_complete();
  ASSERT_TRUE(pair);
  EXPECT_EQ(pair->first, 8);
  EXPECT_EQ(pair->second, 7);
  EXPECT_LE(pairer.high_water(), 16U);
}

TEST(ExactPairer, DuplicateOutOfOrderAndMissingFramesStayBounded)
{
  sim_camera_decoder::ExactPairer<int, int> pairer(2);
  pairer.push_left(3, 30);
  pairer.push_left(1, 10);
  pairer.push_left(2, 20);
  pairer.push_left(2, 21);
  pairer.push_right(2, 22);
  auto pair = pairer.take_newest_complete();
  ASSERT_TRUE(pair);
  EXPECT_EQ(pair->first, 21);
  EXPECT_LE(pairer.size(), 4U);
  EXPECT_GT(pairer.dropped(), 0U);
  EXPECT_LE(pairer.high_water(), 4U);
}
