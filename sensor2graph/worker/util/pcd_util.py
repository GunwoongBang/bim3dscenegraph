"""
Point-cloud utility functions for SENSOR2GRAPH.
"""

from pathlib import Path

import numpy as np
import open3d as o3d


# =========================================================================
# Helper function
# =========================================================================
def _extract_planes_ransac(
    cloud,
    distance_threshold=0.02,
    min_inliers=500,
    max_planes=50,
    num_iterations=1000,
):
    """Extract planar groups from a point cloud using iterative RANSAC."""
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


def write_point_cloud(cloud, input_path):
    """Write a cleaned cloud to {stem}{suffix}{ext} and return its path."""

    src = Path(input_path)
    output_path = src.with_name(f"{src.stem}_cleaned{src.suffix}")
    o3d.io.write_point_cloud(str(output_path), cloud, write_ascii=True)
    return output_path


def count_points(cloud):
    """Return point count for an Open3D point cloud."""
    return len(np.asarray(cloud.points))


def detect_ground_plane(
    cloud,
    distance_threshold=0.02,
    min_inliers=1000,
    num_iterations=1000,
    normal_z_threshold=0.85,
    max_attempts=5,
):
    """Detect a horizontal floor-like plane using the shared RANSAC extractor."""
    plane_groups, _ = _extract_planes_ransac(
        cloud,
        distance_threshold=distance_threshold,
        min_inliers=min_inliers,
        max_planes=max_attempts,
        num_iterations=num_iterations,
    )

    for plane_group in plane_groups:
        normal = plane_group["normal"]
        if abs(normal[2]) >= normal_z_threshold:
            inlier_indices = plane_group["inlier_indices"]
            inlier_points = np.asarray(cloud.points)[inlier_indices]
            centroid_z = float(inlier_points[:, 2].mean())
            return {
                "plane_model": plane_group["plane_model"],
                "normal": normal,
                "inlier_indices": inlier_indices,
                "point_count": plane_group["point_count"],
                "centroid_z": centroid_z,
            }

    return None


def extract_plane_groups(
    cloud,
    distance_threshold=0.02,
    min_inliers=500,
    max_planes=50,
    num_iterations=1000,
):
    """Extract all planar groups from a point cloud using iterative RANSAC."""
    return _extract_planes_ransac(
        cloud,
        distance_threshold=distance_threshold,
        min_inliers=min_inliers,
        max_planes=max_planes,
        num_iterations=num_iterations,
    )
