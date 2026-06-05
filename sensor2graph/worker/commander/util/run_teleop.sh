#!/bin/bash
# Terminal 3: Keyboard teleoperation to drive the robot.
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../ifc2pointcloud" && pwd)"
cd "$WS_DIR"

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 run teleop_twist_keyboard teleop_twist_keyboard
