#include "autonomous_racing_core/midpoint_planner.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <limits>

namespace autonomous_racing_core
{
namespace
{

std::vector<ConePoint> ordered(const std::vector<ConePoint> & input)
{
  std::vector<ConePoint> result;
  result.reserve(input.size());
  for (const auto & point : input) {
    if (std::isfinite(point.x) && std::isfinite(point.y) &&
      std::isfinite(point.confidence) && point.x > 0.0)
    {
      auto copy = point;
      copy.confidence = std::clamp(copy.confidence, 0.0, 1.0);
      result.push_back(copy);
    }
  }
  std::sort(result.begin(), result.end(),
    [](const auto & a, const auto & b) {return a.x < b.x;});
  return result;
}

}  // namespace

MidpointPlanner::MidpointPlanner(double track_width, double exploration_speed)
: track_width_(track_width), exploration_speed_(exploration_speed)
{
  if (!std::isfinite(track_width_) || track_width_ <= 0.0 ||
    !std::isfinite(exploration_speed_) || exploration_speed_ < 0.0)
  {
    throw std::invalid_argument("planner limits must be finite and valid");
  }
}

PathCandidate MidpointPlanner::build(
  const std::vector<ConePoint> & left,
  const std::vector<ConePoint> & right,
  const std::string & frame_id,
  double stamp,
  std::uint64_t revision) const
{
  const auto left_ordered = ordered(left);
  const auto right_ordered = ordered(right);
  PathCandidate result;
  result.frame_id = frame_id;
  result.stamp = stamp;
  result.revision = revision;
  result.mode = 0;  // RacingPath::ROLLING
  result.closed_loop = false;
  const auto count = std::max(left_ordered.size(), right_ordered.size());
  result.points.reserve(count);
  const auto half_width = track_width_ / 2.0;
  for (std::size_t i = 0; i < count; ++i) {
    PathPoint point;
    if (i < left_ordered.size() && i < right_ordered.size()) {
      point.x = (left_ordered[i].x + right_ordered[i].x) / 2.0;
      point.y = (left_ordered[i].y + right_ordered[i].y) / 2.0;
      point.confidence = std::min(left_ordered[i].confidence,
                                  right_ordered[i].confidence);
      point.state = point.confidence >= 0.75 ? 0 : 1;  // trusted/degraded
    } else if (i < left_ordered.size()) {
      point.x = left_ordered[i].x;
      point.y = left_ordered[i].y - half_width;
      point.confidence = left_ordered[i].confidence * 0.6;
      point.state = 1;
    } else {
      point.x = right_ordered[i].x;
      point.y = right_ordered[i].y + half_width;
      point.confidence = right_ordered[i].confidence * 0.6;
      point.state = 1;
    }
    point.target_speed = exploration_speed_;
    result.points.push_back(point);
  }
  return result;
}

bool MidpointPlanner::usable(const PathCandidate & candidate)
{
  if (candidate.points.empty() || !std::isfinite(candidate.stamp)) {
    return false;
  }
  for (const auto & point : candidate.points) {
    if (!std::isfinite(point.x) || !std::isfinite(point.y) ||
      !std::isfinite(point.target_speed) || !std::isfinite(point.confidence) ||
      point.state == 2 || point.confidence < 0.4)
    {
      return false;
    }
  }
  return true;
}

}  // namespace autonomous_racing_core
