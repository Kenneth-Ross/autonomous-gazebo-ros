#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <stdexcept>
#include <string>
#include <vector>

#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <zstd.h>

namespace sim_camera_encoder
{
inline void append_u32_le(std::vector<uint8_t> & data, uint32_t value)
{
  for (unsigned int shift = 0; shift < 32; shift += 8) {
    data.push_back(static_cast<uint8_t>((value >> shift) & 0xffU));
  }
}

inline sensor_msgs::msg::CompressedImage encode_zstd_image(
  const sensor_msgs::msg::Image & input, int compression_level = 1)
{
  sensor_msgs::msg::CompressedImage output;
  output.header = input.header;
  output.format = "zstd";
  append_u32_le(output.data, input.height);
  append_u32_le(output.data, input.width);
  output.data.push_back(input.is_bigendian);
  append_u32_le(output.data, input.step);
  append_u32_le(output.data, input.encoding.size());
  output.data.insert(output.data.end(), input.encoding.begin(), input.encoding.end());
  const std::size_t metadata = output.data.size();
  output.data.resize(metadata + ZSTD_compressBound(input.data.size()));
  const std::size_t compressed = ZSTD_compress(
    output.data.data() + metadata, output.data.size() - metadata,
    input.data.data(), input.data.size(), compression_level);
  if (ZSTD_isError(compressed)) {
    throw std::runtime_error(
            std::string("Zstd compression failed: ") + ZSTD_getErrorName(compressed));
  }
  output.data.resize(metadata + compressed);
  return output;
}
}  // namespace sim_camera_encoder
