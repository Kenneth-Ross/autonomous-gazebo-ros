#pragma once

#include "autonomous_racing_core/types.hpp"

#include <vector>

namespace autonomous_racing_core
{

class MidpointPlanner {
public:
  explicit MidpointPlanner(double track_width = 6.0, double exploration_speed = 2.0);

  PathCandidate build(
    const std::vector<ConePoint> & left,
    const std::vector<ConePoint> & right,
    const std::string & frame_id,
    double stamp,
    std::uint64_t revision) const;

  static bool usable(const PathCandidate & candidate);

private:
  double track_width_;
  double exploration_speed_;
};

}  // namespace autonomous_racing_core
