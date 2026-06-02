#!/bin/bash
# Run once before launching: exports IFC to SDF and builds the ROS2 workspace.
set -e

WS_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../ifc2pointcloud" && pwd)"
cd "$WS_DIR"

source /opt/ros/humble/setup.bash
colcon build

echo "Done. Ready to launch."
