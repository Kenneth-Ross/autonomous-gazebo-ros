#include "autonomous_racing_core/safety_supervisor.hpp"

#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace autonomous_racing_core
{

SafetySupervisor::SafetySupervisor()
: SafetySupervisor(Config{})
{}

SafetySupervisor::SafetySupervisor(Config config)
: config_(config)
{
  const double values[] = {config_.command_timeout, config_.recorder_timeout,
    config_.max_speed, config_.max_steering};
  for (const auto value : values) {
    if (!std::isfinite(value) || value <= 0.0) {
      throw std::invalid_argument("supervisor limits must be finite and positive");
    }
  }
}

void SafetySupervisor::prepare(const std::string & run_id)
{
  run_id_ = run_id;
  state_ = SupervisorState::READY;
  stop_reason_ = "not_started";
  latched_stop_ = false;
  recorder_seen_ = false;
  candidate_seen_ = false;
  armed_at_ = 0.0;
}

bool SafetySupervisor::start(double now)
{
  if (state_ != SupervisorState::READY || latched_stop_) {
    return false;
  }
  if (config_.require_recorder &&
    (!recorder_seen_ || now - recorder_at_ > config_.recorder_timeout))
  {
    stop_reason_ = "recorder_missing";
    return false;
  }
  state_ = SupervisorState::RACING;
  stop_reason_.clear();
  armed_at_ = now;
  return true;
}

void SafetySupervisor::abort(const std::string & reason)
{
  stop_reason_ = reason.empty() ? "operator_abort" : reason;
  state_ = (stop_reason_ == "operator_abort" || stop_reason_ == "operator_stop") ?
    SupervisorState::ABORTED : SupervisorState::FAILED;
  latched_stop_ = true;
}

bool SafetySupervisor::accept_candidate(
  const CommandCandidate & candidate,
  double now)
{
  // Nodes publish safe invalid candidates while starting. Do not latch a run
  // before explicit start; invalid candidates become hard faults once racing.
  if (state_ != SupervisorState::RACING || latched_stop_) {
    return false;
  }
  if (!candidate.valid || !std::isfinite(candidate.speed) ||
    !std::isfinite(candidate.steering) || candidate.speed < 0.0 ||
    candidate.speed > config_.max_speed ||
    std::abs(candidate.steering) > config_.max_steering)
  {
    abort(candidate.fault_reason.empty() ? "candidate_invalid" : candidate.fault_reason);
    return false;
  }
  candidate_ = candidate;
  candidate_.received_at = now;
  candidate_seen_ = true;
  return true;
}

bool SafetySupervisor::update_recorder(double now, bool healthy)
{
  if (!healthy) {
    if (state_ == SupervisorState::RACING && config_.require_recorder) {
      abort("recorder_unhealthy");
    }
    return false;
  }
  recorder_seen_ = true;
  recorder_at_ = now;
  return true;
}

SupervisorOutput SafetySupervisor::tick(double now)
{
  SupervisorOutput output;
  output.state = state_;
  if (latched_stop_) {
    output.reason = stop_reason_;
    return output;
  }
  if (state_ == SupervisorState::IDLE) {
    output.reason = "not_prepared";
    return output;
  }
  if (state_ != SupervisorState::RACING) {
    output.reason = "not_started";
    return output;
  }
  if (config_.require_recorder &&
    ((!recorder_seen_ && now - armed_at_ > config_.recorder_timeout) ||
    (recorder_seen_ && now - recorder_at_ > config_.recorder_timeout)))
  {
    abort(!recorder_seen_ ? "recorder_missing" : "recorder_stale");
    output.state = state_;
    output.reason = stop_reason_;
    return output;
  }
  if (!candidate_seen_) {
    if (now - armed_at_ <= config_.command_timeout) {
      output.reason = "candidate_missing";
      return output;
    }
    abort("candidate_missing");
    output.state = state_;
    output.reason = stop_reason_;
    return output;
  }
  if (now - candidate_.received_at > config_.command_timeout) {
    abort("candidate_stale");
    output.state = state_;
    output.reason = stop_reason_;
    return output;
  }
  output.speed = candidate_.speed;
  output.steering = candidate_.steering;
  output.reason.clear();
  return output;
}

}  // namespace autonomous_racing_core
