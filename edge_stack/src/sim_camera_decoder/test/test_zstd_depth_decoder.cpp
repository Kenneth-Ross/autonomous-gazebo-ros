#include <cstring>
#include <string>
#include <vector>

#include <gtest/gtest.h>
#include <zstd.h>

#include "sim_camera_decoder/zstd_depth_decoder.hpp"

namespace
{
void append_u32(std::vector<uint8_t> & data, uint32_t value)
{
  for (unsigned int shift = 0; shift < 32; shift += 8) {
    data.push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

sensor_msgs::msg::CompressedImage make_message(const std::vector<uint16_t> & pixels)
{
  sensor_msgs::msg::CompressedImage message;
  message.header.stamp.sec = 42;
  message.header.stamp.nanosec = 123456789;
  message.header.frame_id = "camera_link_optical";
  message.format = "zstd";
  append_u32(message.data, 2);
  append_u32(message.data, 2);
  message.data.push_back(0);
  append_u32(message.data, 4);
  const std::string encoding = "16UC1";
  append_u32(message.data, encoding.size());
  message.data.insert(message.data.end(), encoding.begin(), encoding.end());
  const auto * raw = reinterpret_cast<const uint8_t *>(pixels.data());
  const std::size_t raw_size = pixels.size() * sizeof(uint16_t);
  const std::size_t start = message.data.size();
  message.data.resize(start + ZSTD_compressBound(raw_size));
  const std::size_t compressed = ZSTD_compress(
    message.data.data() + start, message.data.size() - start, raw, raw_size, 1);
  EXPECT_FALSE(ZSTD_isError(compressed));
  message.data.resize(start + compressed);
  return message;
}
}  // namespace

TEST(ZstdDepthDecoder, PreservesHeaderAndPixelsExactly)
{
  const std::vector<uint16_t> pixels{0, 1, 65534, 65535};
  const auto compressed = make_message(pixels);
  sensor_msgs::msg::Image decoded;
  std::string error;
  ASSERT_TRUE(sim_camera_decoder::decode_zstd_image(compressed, decoded, error)) << error;
  EXPECT_EQ(decoded.header, compressed.header);
  EXPECT_EQ(decoded.encoding, "16UC1");
  EXPECT_EQ(decoded.width, 2U);
  EXPECT_EQ(decoded.height, 2U);
  ASSERT_EQ(decoded.data.size(), pixels.size() * sizeof(uint16_t));
  EXPECT_EQ(std::memcmp(decoded.data.data(), pixels.data(), decoded.data.size()), 0);
}

TEST(ZstdDepthDecoder, RejectsMalformedPayload)
{
  sensor_msgs::msg::CompressedImage malformed;
  malformed.format = "zstd";
  malformed.data = {1, 2, 3};
  sensor_msgs::msg::Image decoded;
  std::string error;
  EXPECT_FALSE(sim_camera_decoder::decode_zstd_image(malformed, decoded, error));
  EXPECT_FALSE(error.empty());
}
