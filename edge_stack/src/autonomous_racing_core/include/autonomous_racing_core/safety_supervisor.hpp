#pragma once

#include "autonomous_racing_core/types.hpp"

#include <cstdint>
#include <string>

namespace autonomous_racing_core
{

enum class SupervisorState : std::uint8_t
{
  IDLE = 0,
  PREPARING = 1,
  READY = 2,
  EXPLORING = 3,
  RACING = 4,
  STOPPING = 5,
  COMPLETE = 6,
  FAILED = 7,
  ABORTED = 8,
};

struct SupervisorOutput
{
  double speed{0.0};
  double steering{0.0};
  std::string reason;
  SupervisorState state{SupervisorState::IDLE};
};

class SafetySupervisor {
public:
  struct Config
  {
    double command_timeout{0.2};
    double recorder_timeout{0.5};
    double max_speed{5.0};
    double max_steering{0.6108};
    bool require_recorder{true};
  };

  SafetySupervisor();
  explicit SafetySupervisor(Config config);

  void prepare(const std::string & run_id);
  bool start(double now);
  void abort(const std::string & reason);
  bool accept_candidate(const CommandCandidate & candidate, double now);
  bool update_recorder(double now, bool healthy);
  SupervisorOutput tick(double now);

  SupervisorState state() const {return state_;}
  const std::string & run_id() const {return run_id_;}
  const std::string & stop_reason() const {return stop_reason_;}
  bool latched() const {return latched_stop_;}
  bool recorder_ready(double now) const
  {
    return !config_.require_recorder ||
           (!latched_stop_ && recorder_seen_ &&
           now - recorder_at_ <= config_.recorder_timeout);
  }

private:
  Config config_;
  SupervisorState state_{SupervisorState::IDLE};
  std::string run_id_;
  std::string stop_reason_{"not_prepared"};
  bool latched_stop_{false};
  bool recorder_seen_{false};
  double recorder_at_{0.0};
  bool candidate_seen_{false};
  CommandCandidate candidate_{};
  double armed_at_{0.0};
};

}  // namespace autonomous_racing_core
