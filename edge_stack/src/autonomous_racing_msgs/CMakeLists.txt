cmake_minimum_required(VERSION 3.8)
project(autonomous_racing_msgs)

find_package(ament_cmake REQUIRED)
find_package(rosidl_default_generators REQUIRED)
find_package(builtin_interfaces REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(std_msgs REQUIRED)

set(msg_files
  "msg/ConeEstimate.msg"
  "msg/ConeMap.msg"
  "msg/RacingPathPoint.msg"
  "msg/RacingPath.msg"
  "msg/ControlCandidate.msg"
  "msg/SupervisorStatus.msg"
  "msg/RecorderHeartbeat.msg"
)
set(srv_files
  "srv/PrepareRun.srv"
  "srv/StartRun.srv"
  "srv/AbortRun.srv"
)

rosidl_generate_interfaces(${PROJECT_NAME}
  ${msg_files}
  ${srv_files}
  DEPENDENCIES builtin_interfaces geometry_msgs std_msgs
)

ament_export_dependencies(rosidl_default_runtime)

if(BUILD_TESTING)
  find_package(ament_cmake_pytest REQUIRED)
  ament_add_pytest_test(interface_contract_test
    test/test_interface_contract.py
  )
endif()

ament_package()
