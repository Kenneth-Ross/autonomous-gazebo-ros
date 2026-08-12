uint8 PROVISIONAL=0
uint8 PERSISTENT=1
uint8 QUARANTINED=2

uint64 id
geometry_msgs/PoseWithCovariance pose
float32 detector_score
uint32 observation_count
uint32 distinct_view_count
builtin_interfaces/Time last_observed
float32 depth_quality
float32 pose_quality
float32 association_confidence
uint8 state
