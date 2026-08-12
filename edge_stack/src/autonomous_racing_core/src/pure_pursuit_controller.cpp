#include "autonomous_racing_core/pure_pursuit_controller.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>
#include <limits>

namespace autonomous_racing_core
{
namespace
{

CommandCandidate invalid(const char *reason)
{
  CommandCandidate result;
  result.valid = false;
  result.fault_reason = reason;
  return result;
}

}  // namespace

PurePursuitController::PurePursuitController()
: PurePursuitController(Config{})
{}

PurePursuitController::PurePursuitController(Config config)
: config_(config)
{
  if (!std::isfinite(config_.wheelbase) || config_.wheelbase <= 0.0 ||
    !std::isfinite(config_.max_steering) || config_.max_steering <= 0.0 ||
    !std::isfinite(config_.freshness_timeout) || config_.freshness_timeout <= 0.0)
  {
    throw std::invalid_argument("controller limits must be finite and positive");
  }
}

CommandCandidate PurePursuitController::compute(
  const PathCandidate & path,
  const VehiclePose & pose,
  double current_speed,
  double now) const
{
  if (path.points.empty()) {
    return invalid("path_empty");
  }
  if (!std::isfinite(path.stamp) || now - path.stamp > config_.freshness_timeout) {
    return invalid("path_stale");
  }
  if (now - path.stamp < -0.05) {
    return invalid("path_clock");
  }
  if (!std::isfinite(current_speed)) {
    return invalid("odometry_invalid");
  }
  const bool local = path.frame_id == "base_link" || path.frame_id == "ackermann_car";
  const double car_x = local ? 0.0 : pose.x;
  const double car_y = local ? 0.0 : pose.y;
  const double car_yaw = local ? 0.0 : pose.yaw;
  const double lookahead = std::clamp(
    config_.lookahead + config_.lookahead_gain * std::abs(current_speed),
    config_.min_lookahead, config_.max_lookahead);
  std::size_t closest = 0;
  double closest_distance = std::numeric_limits<double>::infinity();
  for (std::size_t i = 0; i < path.points.size(); ++i) {
    const double distance = std::hypot(path.points[i].x - car_x,
                                       path.points[i].y - car_y);
    if (distance < closest_distance) {
      closest_distance = distance;
      closest = i;
    }
  }
  std::size_t goal = path.points.size() - 1;
  for (std::size_t i = closest; i < path.points.size(); ++i) {
    if (std::hypot(path.points[i].x - car_x, path.points[i].y - car_y) >= lookahead) {
      goal = i;
      break;
    }
  }
  const auto & point = path.points[goal];
  if (point.state == 2 || point.confidence < 0.4 ||
    !std::isfinite(point.target_speed))
  {
    return invalid("path_unsafe");
  }
  const double alpha = std::atan2(point.y - car_y, point.x - car_x) - car_yaw;
  const double normalized = std::atan2(std::sin(alpha), std::cos(alpha));
  const double raw_steering = std::atan2(
    2.0 * config_.wheelbase * std::sin(normalized), lookahead);
  CommandCandidate result;
  result.speed = std::max(0.0, point.target_speed);
  result.steering = std::clamp(raw_steering, -config_.max_steering,
                               config_.max_steering);
  result.confidence = point.confidence;
  result.path_revision = path.revision;
  result.valid = true;
  result.received_at = now;
  return result;
}

}  // namespace autonomous_racing_core
