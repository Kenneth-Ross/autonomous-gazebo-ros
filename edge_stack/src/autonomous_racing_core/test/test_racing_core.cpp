#include "autonomous_racing_core/midpoint_planner.hpp"
#include "autonomous_racing_core/pure_pursuit_controller.hpp"
#include "autonomous_racing_core/safety_supervisor.hpp"

#include <gtest/gtest.h>

using autonomous_racing_core::CommandCandidate;
using autonomous_racing_core::ConePoint;
using autonomous_racing_core::MidpointPlanner;
using autonomous_racing_core::PathCandidate;
using autonomous_racing_core::PurePursuitController;
using autonomous_racing_core::SafetySupervisor;
using autonomous_racing_core::SupervisorState;

TEST(MidpointPlanner, RefusesStraightFallbackWithoutCones)
{
  MidpointPlanner planner;
  const auto result = planner.build({}, {}, "base_link", 1.0, 1);
  EXPECT_TRUE(result.points.empty());
  EXPECT_FALSE(MidpointPlanner::usable(result));
}

TEST(MidpointPlanner, PairedAndSingleSideConfidence)
{
  MidpointPlanner planner;
  const auto result = planner.build(
    {{2.0, 1.0, 1.0}, {4.0, 1.0, 1.0}},
    {{2.0, -1.0, 1.0}}, "base_link", 1.0, 4);
  ASSERT_EQ(result.points.size(), 2U);
  EXPECT_DOUBLE_EQ(result.points[0].y, 0.0);
  EXPECT_EQ(result.points[0].state, 0U);
  EXPECT_LT(result.points[1].confidence, 0.75);
  EXPECT_EQ(result.points[1].state, 1U);
}

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

TEST(PurePursuitController, RejectsStaleOrUnsafePath)
{
  PathCandidate stale;
  stale.frame_id = "base_link";
  stale.stamp = 1.0;
  stale.points = {{2.0, 0.0, 2.0, 1.0, 0}};
  PurePursuitController controller;
  EXPECT_FALSE(controller.compute(stale, {}, 0.0, 1.21).valid);
  stale.stamp = 2.0;
  stale.points[0].state = 2;
  EXPECT_FALSE(controller.compute(stale, {}, 0.0, 2.0).valid);
}

TEST(SafetySupervisor, RequiresPrepareStartAndRecorder)
{
  SafetySupervisor supervisor;
  EXPECT_EQ(supervisor.tick(0.0).reason, "not_prepared");
  supervisor.prepare("run-a");
  EXPECT_FALSE(supervisor.start(0.0));
  EXPECT_EQ(supervisor.stop_reason(), "recorder_missing");
  ASSERT_TRUE(supervisor.update_recorder(0.0, true));
  EXPECT_TRUE(supervisor.start(0.0));
  EXPECT_EQ(supervisor.tick(0.1).reason, "candidate_missing");
  EXPECT_EQ(supervisor.tick(0.51).reason, "recorder_stale");
  EXPECT_TRUE(supervisor.latched());
}

TEST(SafetySupervisor, IgnoresStartupInvalidCandidateUntilStart)
{
  SafetySupervisor supervisor;
  CommandCandidate invalid;
  invalid.valid = false;
  invalid.fault_reason = "path_empty";
  EXPECT_FALSE(supervisor.accept_candidate(invalid, 0.0));
  EXPECT_FALSE(supervisor.latched());
  supervisor.prepare("run-startup");
  EXPECT_FALSE(supervisor.accept_candidate(invalid, 0.1));
  EXPECT_FALSE(supervisor.latched());
  ASSERT_TRUE(supervisor.update_recorder(0.1, true));
  ASSERT_TRUE(supervisor.start(0.1));
  EXPECT_FALSE(supervisor.accept_candidate(invalid, 0.1));
  EXPECT_TRUE(supervisor.latched());
  EXPECT_EQ(supervisor.stop_reason(), "path_empty");
}

TEST(SafetySupervisor, OperatorStopIsLatchedAbort)
{
  SafetySupervisor supervisor;
  supervisor.prepare("run-stop");
  supervisor.abort("operator_stop");
  EXPECT_EQ(supervisor.state(), SupervisorState::ABORTED);
  EXPECT_EQ(supervisor.stop_reason(), "operator_stop");
  EXPECT_TRUE(supervisor.latched());
}

TEST(SafetySupervisor, RecorderAndCandidateFreshnessLatch)
{
  SafetySupervisor supervisor;
  supervisor.prepare("run-b");
  ASSERT_TRUE(supervisor.update_recorder(10.0, true));
  EXPECT_TRUE(supervisor.recorder_ready(10.1));
  ASSERT_TRUE(supervisor.start(10.0));
  CommandCandidate candidate;
  candidate.valid = true;
  candidate.speed = 1.0;
  candidate.steering = 0.1;
  ASSERT_TRUE(supervisor.accept_candidate(candidate, 10.0));
  EXPECT_DOUBLE_EQ(supervisor.tick(10.1).speed, 1.0);
  EXPECT_EQ(supervisor.tick(10.21).reason, "candidate_stale");
  EXPECT_FALSE(supervisor.recorder_ready(10.21));
}

TEST(SafetySupervisor, RefusesStartWithoutFreshRecorderHeartbeat)
{
  SafetySupervisor supervisor;
  supervisor.prepare("run-recorder-gate");
  EXPECT_FALSE(supervisor.start(0.0));
  EXPECT_EQ(supervisor.stop_reason(), "recorder_missing");
  EXPECT_FALSE(supervisor.latched());
  ASSERT_TRUE(supervisor.update_recorder(1.0, true));
  EXPECT_TRUE(supervisor.start(1.1));
}
