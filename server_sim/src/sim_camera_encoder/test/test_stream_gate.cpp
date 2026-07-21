#include <gtest/gtest.h>
#include "sim_camera_encoder/stream_gate.hpp"

TEST(StreamGate, IndependentlyControlsStreams)
{
  sim_camera_encoder::StreamGate gate;
  EXPECT_TRUE(gate.rgb());
  EXPECT_TRUE(gate.depth());
  gate.set_rgb(false);
  EXPECT_FALSE(gate.rgb());
  EXPECT_TRUE(gate.depth());
  gate.set_depth(false);
  gate.set_rgb(true);
  EXPECT_TRUE(gate.rgb());
  EXPECT_FALSE(gate.depth());
}
