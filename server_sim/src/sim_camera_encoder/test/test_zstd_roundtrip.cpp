// Copyright 2026 k-dev
#include <zstd.h>

#include <algorithm>
#include <cstdint>
#include <cstring>
#include <random>
#include <string>
#include <vector>

#include <gtest/gtest.h>
#include "sim_camera_encoder/zstd_depth_encoder.hpp"

namespace
{
void expect_round_trip(const std::vector<uint16_t> & input)
{
  sensor_msgs::msg::Image image;
  image.header.stamp.sec = 42;
  image.header.stamp.nanosec = 123456789;
  image.header.frame_id = "camera_link_optical";
  image.height = 800;
  image.width = 1280;
  image.encoding = "16UC1";
  image.step = image.width * sizeof(uint16_t);
  image.data.resize(input.size() * sizeof(uint16_t));
  std::memcpy(image.data.data(), input.data(), image.data.size());
  const auto compressed = sim_camera_encoder::encode_zstd_image(image, 1);
  EXPECT_EQ(compressed.header, image.header);
  EXPECT_EQ(compressed.format, "zstd");
  const size_t metadata = 17U + image.encoding.size();
  std::vector<uint16_t> output(input.size());
  const size_t restored = ZSTD_decompress(
    output.data(), image.data.size(), compressed.data.data() + metadata,
    compressed.data.size() - metadata);
  ASSERT_FALSE(ZSTD_isError(restored));
  EXPECT_EQ(restored, image.data.size());
  EXPECT_EQ(output, input);
}
}  // namespace

TEST(ZstdDepth, LevelOneProductionEnvelopeIsBitExactForRepresentativeFrames)
{
  constexpr size_t pixels = 1280U * 800U;
  std::vector<uint16_t> values(pixels, 0U);
  expect_round_trip(values);
  std::fill(values.begin(), values.end(), 65535U);
  expect_round_trip(values);
  for (size_t i = 0; i < pixels; ++i) {
    values[i] = static_cast<uint16_t>(i % 65536U);
  }
  expect_round_trip(values);
  std::mt19937 generator(12345U);
  std::uniform_int_distribution<uint16_t> distribution(0U, 65535U);
  for (auto & value : values) {
    value = distribution(generator);
  }
  expect_round_trip(values);
}
