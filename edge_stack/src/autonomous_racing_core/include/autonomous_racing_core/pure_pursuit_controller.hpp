#pragma once

#include "autonomous_racing_core/types.hpp"

namespace autonomous_racing_core
{

class PurePursuitController {
public:
  struct Config
  {
    double wheelbase{1.511};
    double lookahead{3.0};
    double lookahead_gain{0.5};
    double min_lookahead{1.5};
    double max_lookahead{8.0};
    double max_steering{0.6108};
    double freshness_timeout{0.2};
  };

  PurePursuitController();
  explicit PurePursuitController(Config config);

  CommandCandidate compute(
    const PathCandidate & path,
    const VehiclePose & pose,
    double current_speed,
    double now) const;

private:
  Config config_;
};

}  // namespace autonomous_racing_core
