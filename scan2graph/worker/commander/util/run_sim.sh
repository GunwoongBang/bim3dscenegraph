#!/bin/bash
# Terminal 1: Gazebo simulation with robot and Velodyne LiDAR.
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../ifc2pointcloud" && pwd)"
cd "$WS_DIR"

source /opt/ros/humble/setup.bash
source install/setup.bash

ros2 launch robot_gazebo robot_sim.launch.py
