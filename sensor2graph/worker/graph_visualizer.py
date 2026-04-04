"""
Point-cloud visualization utilities for SENSOR2GRAPH.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from .util import read_point_cloud, voxel_downsample


def visualize_point_cloud(pc_path, logger=None):
    """
    Visualize a PCD point cloud with Matplotlib.

    Args:
        pc_path: Path to a .pcd file.
        logger: Optional logger for output messages.
    """
    if not Path(pc_path).exists():
        raise FileNotFoundError(f"Point cloud file not found: {pc_path}")

    cloud = read_point_cloud(pc_path)

    # Note: Temporary sampling for visualization
    # It will be deleted later, after a cleaner is reintroduced
    # =========================================================================
    voxel_size = 0.01

    downsampled_cloud = voxel_downsample(cloud, voxel_size)
    # =========================================================================

    points_to_show = np.asarray(downsampled_cloud.points)
    if points_to_show.size == 0:
        raise ValueError(f"No points to visualize: {pc_path}")

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Visualizing point cloud with {len(points_to_show)} points")

    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, projection="3d")
    ax.scatter(
        points_to_show[:, 0],
        points_to_show[:, 1],
        points_to_show[:, 2],
        s=0.4,
        c=points_to_show[:, 2],
        cmap="viridis",
        alpha=0.8,
        linewidths=0,
    )
    ax.set_title(f"Point Cloud Viewer: {Path(pc_path).name}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    mins = points_to_show.min(axis=0)
    maxs = points_to_show.max(axis=0)
    centers = (mins + maxs) / 2.0
    half_range = (maxs - mins).max() / 2.0

    ax.set_xlim(centers[0] - half_range, centers[0] + half_range)
    ax.set_ylim(centers[1] - half_range, centers[1] + half_range)
    ax.set_zlim(centers[2] - half_range, centers[2] + half_range)
    ax.set_box_aspect((1, 1, 1))

    plt.tight_layout()
    plt.show()
