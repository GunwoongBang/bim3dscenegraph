#!/bin/bash
# Manual one-time setup: builds the ROS2 workspace. The pipeline calls colcon build automatically.
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../ifc2pointcloud" && pwd)"
cd "$WS_DIR"

source /opt/ros/humble/setup.bash
colcon build

echo "Done. Ready to launch."
