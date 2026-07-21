// Copyright 2026 k-dev
#include <zstd.h>

#include <algorithm>
#include <cstdint>
#include <random>
#include <vector>

#include <gtest/gtest.h>

namespace
{
void expect_round_trip(const std::vector<uint16_t> & input)
{
  const size_t bytes = input.size() * sizeof(uint16_t);
  std::vector<uint8_t> compressed(ZSTD_compressBound(bytes));
  const size_t compressed_size = ZSTD_compress(
    compressed.data(), compressed.size(), input.data(), bytes, 1);
  ASSERT_FALSE(ZSTD_isError(compressed_size));
  std::vector<uint16_t> output(input.size());
  const size_t restored = ZSTD_decompress(
    output.data(), bytes, compressed.data(), compressed_size);
  ASSERT_FALSE(ZSTD_isError(restored));
  EXPECT_EQ(restored, bytes);
  EXPECT_EQ(output, input);
}
}  // namespace

TEST(ZstdDepth, LevelOneIsBitExactForRepresentativeFrames)
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
