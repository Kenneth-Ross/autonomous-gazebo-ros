#pragma once

#include <cstdint>
#include <string>
#include <vector>

namespace autonomous_racing_core
{

struct ConePoint
{
  double x{0.0};
  double y{0.0};
  double confidence{1.0};
};

struct PathPoint
{
  double x{0.0};
  double y{0.0};
  double target_speed{0.0};
  double confidence{0.0};
  std::uint8_t state{2};
};

struct PathCandidate
{
  std::string frame_id;
  double stamp{0.0};
  std::uint64_t revision{0};
  std::uint8_t mode{0};
  bool closed_loop{false};
  std::vector<PathPoint> points;
};

struct VehiclePose
{
  double x{0.0};
  double y{0.0};
  double yaw{0.0};
};

struct CommandCandidate
{
  double speed{0.0};
  double steering{0.0};
  double confidence{0.0};
  std::uint64_t path_revision{0};
  bool valid{false};
  std::string fault_reason;
  double received_at{0.0};
};

}  // namespace autonomous_racing_core
