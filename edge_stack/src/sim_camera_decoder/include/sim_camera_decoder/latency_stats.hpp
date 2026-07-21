#pragma once

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include <stdexcept>
#include <vector>

namespace sim_camera_decoder
{
class LatencyStats
{
public:
  explicit LatencyStats(std::size_t maximum_milliseconds = 10000)
  : bins_(maximum_milliseconds + 1, 0)
  {
    if (maximum_milliseconds == 0) {
      throw std::invalid_argument("latency range must be positive");
    }
  }

  void add(double milliseconds)
  {
    if (!std::isfinite(milliseconds) || milliseconds < 0.0) {
      return;
    }
    const auto rounded_up = static_cast<std::size_t>(std::ceil(milliseconds));
    const auto index = rounded_up < bins_.size() ? rounded_up : bins_.size() - 1;
    ++bins_[index];
    ++size_;
  }

  std::size_t size() const {return size_;}

  double percentile(double fraction) const
  {
    if (size_ == 0 || fraction <= 0.0 || fraction > 1.0) {
      throw std::invalid_argument("invalid percentile request");
    }
    const auto rank = static_cast<std::size_t>(std::ceil(fraction * size_));
    std::size_t cumulative = 0;
    for (std::size_t index = 0; index < bins_.size(); ++index) {
      cumulative += bins_[index];
      if (cumulative >= rank) {
        return static_cast<double>(index);
      }
    }
    throw std::logic_error("latency histogram is inconsistent");
  }

  void clear()
  {
    std::fill(bins_.begin(), bins_.end(), 0);
    size_ = 0;
  }

private:
  std::vector<std::uint64_t> bins_;
  std::size_t size_{0};
};
}  // namespace sim_camera_decoder
