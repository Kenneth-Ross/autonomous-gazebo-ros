#pragma once

#include <cstddef>
#include <cstdint>
#include <cstring>
#include <limits>
#include <string>

#include <sensor_msgs/msg/compressed_image.hpp>
#include <sensor_msgs/msg/image.hpp>
#include <zstd.h>

namespace sim_camera_decoder
{
inline uint32_t read_u32_le(const uint8_t * data)
{
  return static_cast<uint32_t>(data[0]) |
         (static_cast<uint32_t>(data[1]) << 8U) |
         (static_cast<uint32_t>(data[2]) << 16U) |
         (static_cast<uint32_t>(data[3]) << 24U);
}

inline bool decode_zstd_image(
  const sensor_msgs::msg::CompressedImage & input,
  sensor_msgs::msg::Image & output,
  std::string & error)
{
  constexpr std::size_t fixed_metadata = 17U;
  if (input.format != "zstd" || input.data.size() < fixed_metadata) {
    error = "invalid zstd image metadata";
    return false;
  }
  const uint32_t height = read_u32_le(&input.data[0]);
  const uint32_t width = read_u32_le(&input.data[4]);
  const uint32_t step = read_u32_le(&input.data[9]);
  const uint32_t encoding_size = read_u32_le(&input.data[13]);
  if (height == 0U || width == 0U || step == 0U ||
    encoding_size > input.data.size() - fixed_metadata)
  {
    error = "invalid zstd image dimensions or encoding";
    return false;
  }
  const std::size_t metadata = fixed_metadata + encoding_size;
  if (metadata >= input.data.size() ||
    height > std::numeric_limits<std::size_t>::max() / step)
  {
    error = "invalid zstd image payload size";
    return false;
  }
  const std::size_t output_size = static_cast<std::size_t>(height) * step;
  output.data.resize(output_size);
  const std::size_t decoded = ZSTD_decompress(
    output.data.data(), output.data.size(),
    input.data.data() + metadata, input.data.size() - metadata);
  if (ZSTD_isError(decoded) || decoded != output_size) {
    error = ZSTD_isError(decoded) ? ZSTD_getErrorName(decoded) : "unexpected decoded size";
    output.data.clear();
    return false;
  }
  output.header = input.header;
  output.height = height;
  output.width = width;
  output.is_bigendian = input.data[8];
  output.step = step;
  output.encoding.assign(
    reinterpret_cast<const char *>(input.data.data() + fixed_metadata), encoding_size);
  return true;
}
}  // namespace sim_camera_decoder
