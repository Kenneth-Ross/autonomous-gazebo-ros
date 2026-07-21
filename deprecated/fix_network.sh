#!/bin/bash
sudo ip link set eno1 txqueuelen 10000
sudo ip link set lo txqueuelen 10000
sudo sysctl -w net.core.wmem_default=16777216
sudo sysctl -w net.core.rmem_default=16777216
sudo sysctl -w net.core.wmem_max=16777216
sudo sysctl -w net.core.rmem_max=16777216
echo "Network buffers increased successfully!"
