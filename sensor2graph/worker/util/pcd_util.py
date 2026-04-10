from pathlib import Path

import numpy as np
import open3d as o3d


# =========================================================================
# Point cloud utilities
# =========================================================================
def _count_points(cloud):
    """Return point count for an Open3D point cloud."""
    return len(np.asarray(cloud.points))


# def voxel_downsample(cloud, voxel_size):
#     """Apply voxel downsampling to reduce point density uniformly."""
#     if voxel_size <= 0:
#         return cloud
#     return cloud.voxel_down_sample(voxel_size=voxel_size)

# def remove_statistical_outliers(cloud, nb_neighbors, std_ratio):
#     """Remove points that are far from their local neighborhood."""
#     if nb_neighbors <= 0 or std_ratio <= 0:
#         return cloud

#     filtered, _ = cloud.remove_statistical_outlier(
#         nb_neighbors=nb_neighbors,
#         std_ratio=std_ratio,
#     )
#     return filtered


def read_point_cloud(pcd_path: Path) -> o3d.geometry.PointCloud:
    """
    Load a point cloud from a PCD file using Open3D.

    Args:
        pcd_path: Path to the input PCD file.

    Returns:
        cloud: Open3D PointCloud object containing the loaded point cloud data.
    """

    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    cloud = o3d.io.read_point_cloud(str(path))
    if cloud.is_empty():
        raise ValueError(f"Point cloud is empty or unreadable: {path}")
    return cloud


def extract_plane_groups(
    cloud: o3d.geometry.PointCloud,
    distance_threshold: float,
    min_inliers: int, max_planes: int,
    num_iterations: int,
) -> list[dict]:
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
    """
    if cloud.is_empty():
        return [], cloud

    working_cloud = cloud
    working_indices = np.arange(_count_points(cloud))
    plane_groups = []

    for plane_id in range(max_planes):
        if _count_points(working_cloud) < min_inliers:
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

    return plane_groups


def make_plane_colors(plane_groups: list[dict], n_points: int) -> np.ndarray:
    """
    Create deterministic colors for plane visualization.

    Args:
        plane_groups: List of plane groups with 'segment_id' and 'inlier_indices'.
        n_points: Total number of points in the original cloud.

    Returns:
        colors: Nx3 array of RGB colors for each point, with planes colored and others gray
    """
    colors = np.ones((n_points, 3), dtype=np.float64) * 0.35
    for plane_group in plane_groups:
        segment_id = plane_group["segment_id"]
        rng = np.random.default_rng(1337 + int(segment_id))
        colors[plane_group["inlier_indices"]] = rng.random(3) * 0.6 + 0.25
    return colors


def pick_seed_point(cloud, colors: np.ndarray, window_name: str = "Plane Picker") -> int | None:
    """
    Open a selection-capable viewer and return one picked point index.

    Args:
        cloud: Open3D point cloud to visualize for picking.
        colors: Nx3 array of RGB colors for visualizing the cloud.
        window_name: Title for the visualization window.

    Returns:
        Int: The index of the picked point, or None if no point was picked.
    """
    picker_cloud = o3d.geometry.PointCloud()
    picker_cloud.points = cloud.points
    picker_cloud.colors = o3d.utility.Vector3dVector(colors)

    visualizer = o3d.visualization.VisualizerWithEditing()
    visualizer.create_window(window_name=window_name)
    visualizer.add_geometry(picker_cloud)
    visualizer.run()
    picked = visualizer.get_picked_points()
    visualizer.destroy_window()

    if not picked:
        return None
    return int(picked[0])


def print_ifc_wall_options(walls):
    """
    Print IFC wall options as numbered menu entries.

    Args:
        walls: List of IfcWall elements from the IFC model.
    """
    print("\nAvailable IFC wall labels:")
    for idx, wall in enumerate(walls, start=1):
        wall_name = getattr(wall, "Name", None) or "Unnamed"
        wall_id = getattr(wall, "GlobalId", None) or "NoGlobalId"
        print(f"  {idx}. IfcWall: {wall_id} ({wall_name})")
