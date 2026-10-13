#include "autonomous_racing_core/pure_pursuit_controller.hpp"
#include "autonomous_racing_core/safety_supervisor.hpp"

#include <gtest/gtest.h>

using autonomous_racing_core::CommandCandidate;
using autonomous_racing_core::PathCandidate;
using autonomous_racing_core::PurePursuitController;
using autonomous_racing_core::SafetySupervisor;

TEST(PurePursuitController, ClampsSteeringAndUsesRevision)
{
  PathCandidate path;
  path.frame_id = "base_link";
  path.stamp = 10.0;
  path.revision = 9;
  path.points = {{2.0, 0.0, 2.0, 1.0, 0}, {3.0, 5.0, 2.0, 1.0, 0}};
  PurePursuitController controller;
  const auto command = controller.compute(path, {}, 0.0, 10.1);
  ASSERT_TRUE(command.valid);
  EXPECT_LE(command.steering, 0.6108);
  EXPECT_GE(command.steering, -0.6108);
  EXPECT_EQ(command.path_revision, 9U);
}

TEST(SafetySupervisor, DelayedValidCandidateExpiresFromSourceStamp)
{
  SafetySupervisor supervisor;
  supervisor.prepare("delayed");
  ASSERT_TRUE(supervisor.update_recorder(10.0, "delayed", true, 10.0));
  ASSERT_TRUE(supervisor.start(10.0));
  CommandCandidate candidate;
  candidate.valid = true;
  candidate.speed = 1.0;
  ASSERT_TRUE(supervisor.accept_candidate(candidate, 10.19, 10.0));
  EXPECT_EQ(supervisor.tick(10.21).reason, "candidate_stale");
}

TEST(SafetySupervisor, StaleRecorderDeliveryInvalidatesPriorHeartbeat)
{
  SafetySupervisor supervisor;
  supervisor.prepare("delayed-recorder");
  ASSERT_TRUE(supervisor.update_recorder(
      10.0, "delayed-recorder", true, 10.0));
  ASSERT_TRUE(supervisor.start(10.0));
  EXPECT_FALSE(supervisor.update_recorder(
      10.6, "delayed-recorder", true, 10.0));
  EXPECT_FALSE(supervisor.recorder_ready(10.6));
  EXPECT_TRUE(supervisor.latched());
  EXPECT_EQ(supervisor.stop_reason(), "recorder_stale");
}

TEST(MessageStamp, RejectsZeroStaleFutureAndNonFiniteTimes)
{
  using autonomous_racing_core::is_fresh_message_stamp;
  EXPECT_TRUE(is_fresh_message_stamp(10.0, 10.1, 0.2));
  EXPECT_FALSE(is_fresh_message_stamp(0.0, 10.1, 0.2));
  EXPECT_FALSE(is_fresh_message_stamp(9.0, 10.1, 0.2));
  EXPECT_FALSE(is_fresh_message_stamp(10.2, 10.1, 0.2));
  EXPECT_FALSE(is_fresh_message_stamp(NAN, 10.1, 0.2));
}
