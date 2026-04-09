"""
Point-cloud utility functions for SENSOR2GRAPH.
"""

from pathlib import Path

import numpy as np
import open3d as o3d


# =========================================================================
# Point cloud utilities
# =========================================================================
def read_point_cloud(pcd_path):
    """Load a point cloud from a PCD file using Open3D."""

    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    cloud = o3d.io.read_point_cloud(str(path))
    if cloud.is_empty():
        raise ValueError(f"Point cloud is empty or unreadable: {path}")
    return cloud


def voxel_downsample(cloud, voxel_size):
    """Apply voxel downsampling to reduce point density uniformly."""
    if voxel_size <= 0:
        return cloud
    return cloud.voxel_down_sample(voxel_size=voxel_size)


def remove_statistical_outliers(cloud, nb_neighbors, std_ratio):
    """Remove points that are far from their local neighborhood."""
    if nb_neighbors <= 0 or std_ratio <= 0:
        return cloud

    filtered, _ = cloud.remove_statistical_outlier(
        nb_neighbors=nb_neighbors,
        std_ratio=std_ratio,
    )
    return filtered


def count_points(cloud):
    """Return point count for an Open3D point cloud."""
    return len(np.asarray(cloud.points))


def extract_plane_groups(
    cloud,
    distance_threshold,
    min_inliers,
    max_planes,
    num_iterations,
):
    """
    Extract all planar groups from a point cloud using iterative RANSAC.

    Args:
        cloud: Open3D point cloud to segment.
        distance_threshold: RANSAC distance threshold for plane fitting.
        min_inliers: Minimum number of inliers to consider a valid plane.
        max_planes: Maximum number of planes to extract.
        num_iterations: RANSAC iterations for plane fitting.

    Returns:
        plane_groups: List of dicts with plane parameters and inlier indices.
        residual_cloud: Open3D point cloud of remaining points after plane extraction.
    """
    if cloud.is_empty():
        return [], cloud

    working_cloud = cloud
    working_indices = np.arange(count_points(cloud))
    plane_groups = []

    for plane_id in range(max_planes):
        if count_points(working_cloud) < min_inliers:
            break

        plane_model, inliers = working_cloud.segment_plane(
            distance_threshold=distance_threshold,
            ransac_n=3,
            num_iterations=num_iterations,
        )

        if len(inliers) < min_inliers:
            break

        normal = np.asarray(plane_model[:3], dtype=np.float64)
        normal_norm = np.linalg.norm(normal)
        if normal_norm == 0:
            working_cloud = working_cloud.select_by_index(inliers, invert=True)
            working_indices = np.delete(working_indices, inliers)
            continue

        normal = normal / normal_norm
        inlier_indices = working_indices[np.asarray(inliers)]
        plane_groups.append(
            {
                "segment_id": plane_id,
                "plane_model": plane_model,
                "normal": normal,
                "inlier_indices": inlier_indices,
                "point_count": len(inliers),
            }
        )

        working_cloud = working_cloud.select_by_index(inliers, invert=True)
        working_indices = np.delete(working_indices, inliers)

    return plane_groups, working_cloud
