// Copyright 2026 k-dev
#pragma once

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace sim_camera_encoder
{
inline uint16_t metres_to_millimetres(const float metres)
{
  if (!std::isfinite(metres) || metres <= 0.0F) {
    return 0U;
  }
  const double millimetres = static_cast<double>(metres) * 1000.0;
  if (millimetres >= 65535.0) {
    return 65535U;
  }
  return static_cast<uint16_t>(std::lround(millimetres));
}
}  // namespace sim_camera_encoder
