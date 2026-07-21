# Unified Control Packet for Ackermann Vehicle
# Ensures synchronization of all control parameters

std_msgs/Header header

float32 throttle      # 0.0 to 1.0
float32 brake         # 0.0 to 1.0
float32 steering      # -1.0 to 1.0 (normalized)
float32 target_vel    # Target velocity in m/s for ECU feedback loop
