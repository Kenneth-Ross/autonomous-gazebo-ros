uint8 STARTING=0
uint8 READY=1
uint8 RECORDING=2
uint8 STOPPING=3
uint8 COMPLETE=4
uint8 ABORTED=5
uint8 INCOMPLETE=6

std_msgs/Header header
string run_id
uint8 state
bool bag_healthy
string detail
