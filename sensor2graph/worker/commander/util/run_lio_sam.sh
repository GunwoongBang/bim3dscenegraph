#!/bin/bash
# Terminal 2: LIO-SAM lidar-inertial odometry and mapping.
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../ifc2pointcloud" && pwd)"
cd "$WS_DIR"

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch lio_sam run.launch.py
