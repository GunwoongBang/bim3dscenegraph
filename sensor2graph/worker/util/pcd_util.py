"""
Point-cloud utility functions for SENSOR2GRAPH.
"""

from pathlib import Path

import numpy as np
import open3d as o3d

from ..geometry import extract_mesh_from_shape


# =========================================================================
# Point cloud cleaning utilities
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


def compute_ifc_bounds(ifc_model, include_types=None):
    """Compute global IFC-aligned bounds from geometry vertices."""
    types = include_types or ("IfcWall", "IfcSlab")

    vertices_blocks = []
    for ifc_type in types:
        try:
            elements = ifc_model.by_type(ifc_type)
        except RuntimeError:
            continue

        for element in elements:
            try:
                vertices, _, _ = extract_mesh_from_shape(element)
            except Exception:
                continue
            if vertices.size > 0:
                vertices_blocks.append(vertices)

    if not vertices_blocks:
        return None

    all_vertices = np.vstack(vertices_blocks)
    mins = all_vertices.min(axis=0)
    maxs = all_vertices.max(axis=0)
    return {
        "min_x": float(mins[0]),
        "max_x": float(maxs[0]),
        "min_y": float(mins[1]),
        "max_y": float(maxs[1]),
        "min_z": float(mins[2]),
        "max_z": float(maxs[2]),
    }


def keep_points_inside_ifc_bounds(cloud, bounds, margin):
    """Keep only points inside IFC-derived axis-aligned bounds with margin."""
    if bounds is None:
        return cloud

    points = np.asarray(cloud.points)
    if points.size == 0:
        return cloud

    mask = (
        (points[:, 0] >= bounds["min_x"] - margin)
        & (points[:, 0] <= bounds["max_x"] + margin)
        & (points[:, 1] >= bounds["min_y"] - margin)
        & (points[:, 1] <= bounds["max_y"] + margin)
        & (points[:, 2] >= bounds["min_z"] - margin)
        & (points[:, 2] <= bounds["max_z"] + margin)
    )

    kept_indices = np.where(mask)[0].tolist()
    if not kept_indices:
        return cloud

    return cloud.select_by_index(kept_indices)


def write_point_cloud(cloud, input_path):
    """Write a cleaned cloud to {stem}{suffix}{ext} and return its path."""

    src = Path(input_path)
    output_path = src.with_name(f"{src.stem}_cleaned{src.suffix}")
    o3d.io.write_point_cloud(str(output_path), cloud, write_ascii=True)
    return output_path


def count_points(cloud):
    """Return point count for an Open3D point cloud."""
    return len(np.asarray(cloud.points))

# =========================================================================
# Point cloud segmentation utilities
# =========================================================================
