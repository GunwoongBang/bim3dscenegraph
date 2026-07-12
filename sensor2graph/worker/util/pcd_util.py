from dataclasses import dataclass, field
from pathlib import Path

import glob
import os

import numpy as np
import open3d as o3d


def _count_points(cloud) -> int:
    """
    Return point count for an Open3D point cloud.

    Args:
        cloud: Open3D PointCloud object.

    Returns:
        int: Number of points in the cloud.
    """
    return len(np.asarray(cloud.points))


def read_point_cloud(pcd_model: Path) -> o3d.geometry.PointCloud:
    """
    Load a point cloud from a PCD file using Open3D.

    Args:
        pcd_model: Path to the input PCD file.

    Returns:
        cloud: Open3D PointCloud object containing the loaded point cloud data.
    """

    if not pcd_model.exists():
        raise FileNotFoundError(f"Point cloud file not found: {pcd_model}")

    cloud = o3d.io.read_point_cloud(str(pcd_model))
    if cloud.is_empty():
        raise ValueError(f"Point cloud is empty or unreadable: {pcd_model}")
    return cloud


# ========================================================================
# Point cloud preprocessing utilities (cleaning, downsampling, outlier removal)
# ========================================================================
def floor_removal(pcd_model: Path, cloud, floor_z_cutoff: float) -> Path:
    """
    Remove points below a certain Z value to eliminate floor points.

    Args:
        pcd_model: Path to the original PCD file (used for naming the output).
        cloud: Open3D point cloud to process.
        floor_z_cutoff: Z value below which points are considered floor and removed.

    Returns:
        cleaned_path: Path to the new PCD file without floor points.
    """
    points = cloud.points
    keep_indices = [idx for idx, point in enumerate(
        points) if point[2] > floor_z_cutoff]
    cleaned_cloud = cloud.select_by_index(keep_indices)

    cleaned_path = pcd_model.with_name(
        f"{pcd_model.stem}_cleaned{pcd_model.suffix}")
    o3d.io.write_point_cloud(
        str(cleaned_path), cleaned_cloud, write_ascii=True)

    return cleaned_path


# def voxel_downsample(cloud, voxel_size):
#     if voxel_size <= 0:
#         return cloud
#     return cloud.voxel_down_sample(voxel_size=voxel_size)


# def remove_statistical_outliers(cloud, nb_neighbors, std_ratio):
#     if nb_neighbors <= 0 or std_ratio <= 0:
#         return cloud

#     filtered, _ = cloud.remove_statistical_outlier(
#         nb_neighbors=nb_neighbors,
#         std_ratio=std_ratio,
#     )
#     return filtered


# =========================================================================
# Point cloud filtering utilities (plane segmentation)
# =========================================================================
def extract_plane_groups(
    cloud: o3d.geometry.PointCloud,
    distance_threshold: float,
    min_inliers: int,
    max_planes: int,
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

        # Planarity residual: RMS perpendicular distance of inliers to the
        # fitted plane (metres). Proves the cluster is genuinely flat.
        inlier_points = np.asarray(working_cloud.points)[np.asarray(inliers)]
        signed_dist = inlier_points @ normal + plane_model[3] / normal_norm
        rms_residual = float(np.sqrt(np.mean(signed_dist ** 2)))

        plane_groups.append(
            {
                "plane_id": plane_id,
                "plane_model": plane_model,
                "normal": normal,
                "inlier_indices": inlier_indices,
                "point_count": len(inliers),
                "rms_residual": rms_residual,
            }
        )

        working_cloud = working_cloud.select_by_index(inliers, invert=True)
        working_indices = np.delete(working_indices, inliers)

    return plane_groups


def make_plane_colors(plane_groups: list[dict], n_points: int) -> np.ndarray:
    """
    Create deterministic colors for plane visualization.

    Args:
        plane_groups: List of plane groups with 'plane_id' and 'inlier_indices'.
        n_points: Total number of points in the original cloud.

    Returns:
        colors: Nx3 array of RGB colors for each point, with planes colored and others gray
    """
    colors = np.ones((n_points, 3), dtype=np.float64) * 0.35
    for plane_group in plane_groups:
        plane_id = plane_group["plane_id"]
        rng = np.random.default_rng(1337 + int(plane_id))
        colors[plane_group["inlier_indices"]] = rng.random(3) * 0.6 + 0.25
    return colors


def pick_seed_point(cloud, colors: np.ndarray) -> int | None:
    """
    Open a selection-capable viewer and return one picked point index.

    Args:
        cloud: Open3D point cloud to visualize for picking.
        colors: Nx3 array of RGB colors for visualizing the cloud.

    Returns:
        Int: The index of the picked point, or None if no point was picked.
    """
    picker_cloud = o3d.geometry.PointCloud()
    picker_cloud.points = cloud.points
    picker_cloud.colors = o3d.utility.Vector3dVector(colors)

    visualizer = o3d.visualization.VisualizerWithEditing()
    visualizer.create_window(window_name="Plane Picker")
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


def compact_point_cloud(input_pcd: Path, index_list: list[int]) -> Path:
    """
    Rewrite a new PCD file containing only the points at the specified indices.

    Args:
        input_pcd: Path to the original PCD file.
        index_list: List of point indices to include in the new PCD.

    Returns:
        output_pcd: Path to the newly created PCD file with filtered points.
    """
    output_pcd = input_pcd.with_name(
        f"{input_pcd.stem}_excluded{input_pcd.suffix}")

    input_cloud = read_point_cloud(input_pcd)
    filtered_cloud = input_cloud.select_by_index(index_list, invert=True)
    o3d.io.write_point_cloud(
        str(output_pcd), filtered_cloud, write_ascii=True)

    return output_pcd

# =========================================================================
# Point cloud registration utilities
# =========================================================================
@dataclass
class IcpStageMetric:
    """Fitness / RMSE snapshot from one coarse-to-fine ICP refinement scale."""
    threshold: float
    fitness: float
    inlier_rmse: float
    correspondences: int


@dataclass
class RegistrationValidation:
    """
    Alignment validation result for the sensor-vs-BIM registration stage.

    Attributes:
        transformation: 4x4 source(IFC) -> target(sensor) transform.
        voxel_size: Voxel size used for downsampling / global registration.
        validation_threshold: ICP correspondence threshold (m) that the
            reported fitness/RMSE are measured at (the "small spatial tolerance").
        fitness: Fraction of reference points with a sensor correspondence
            within validation_threshold (coverage / overlap quality).
        inlier_rmse: Alignment residual (m) over those correspondences.
        max_iteration: Max ICP iterations per refinement scale.
        relative_fitness: ICP convergence criterion on the fitness delta.
        relative_rmse: ICP convergence criterion on the RMSE delta.
        stages: Per-scale coarse-to-fine progression.
    """
    transformation: np.ndarray
    voxel_size: float
    validation_threshold: float
    fitness: float
    inlier_rmse: float
    max_iteration: int
    relative_fitness: float
    relative_rmse: float
    stages: list = field(default_factory=list)

    @property
    def inlier_rmse_mm(self) -> float:
        """Alignment residual reported in millimetres."""
        return self.inlier_rmse * 1000.0

    @property
    def validation_threshold_mm(self) -> float:
        """Correspondence threshold reported in millimetres."""
        return self.validation_threshold * 1000.0

    def report(self) -> str:
        """Render a human-readable multi-line validation summary."""
        lines = [
            "Registration validation (IFC reference -> sensor cloud):",
            f"  ICP correspondence threshold : {self.validation_threshold_mm:.1f} mm",
            f"  Inlier RMSE (residual)       : {self.inlier_rmse_mm:.2f} mm",
            f"  Fitness (coverage)           : {self.fitness:.4f}",
            (
                f"  Convergence                  : max_iter={self.max_iteration}, "
                f"rel_fitness={self.relative_fitness:g}, rel_rmse={self.relative_rmse:g}"
            ),
        ]
        if self.stages:
            lines.append("  Coarse-to-fine progression:")
            for stage in self.stages:
                lines.append(
                    f"    thr={stage.threshold * 1000:8.1f} mm | "
                    f"fitness={stage.fitness:.4f} | "
                    f"rmse={stage.inlier_rmse * 1000:8.2f} mm | "
                    f"corr={stage.correspondences}"
                )
        return "\n".join(lines)


def load_ifc_reference_cloud(
    mesh_dir: Path,
    points_per_m2: float = 500.0,
    min_points: int = 100,
    skip_types: tuple = ("IfcSlab",),
) -> o3d.geometry.PointCloud:
    """
    Sample a merged reference point cloud from IFC-derived OBJ meshes.

    Args:
        mesh_dir: Directory of per-element .obj meshes written by SDF export.
        points_per_m2: Uniform sampling density per unit surface area.
        min_points: Minimum samples per mesh regardless of area.
        skip_types: Filename substrings to skip (e.g. slabs/floors already
            removed from the sensor cloud during cleaning).

    Returns:
        merged: Merged Open3D point cloud sampled from the meshes.
    """
    mesh_dir = Path(mesh_dir)
    if not mesh_dir.is_dir():
        raise FileNotFoundError(f"IFC mesh directory not found: {mesh_dir}")

    merged = o3d.geometry.PointCloud()
    for mesh_file in sorted(glob.glob(os.path.join(str(mesh_dir), "*.obj"))):
        name = os.path.basename(mesh_file)
        if any(skip in name for skip in skip_types):
            continue
        mesh = o3d.io.read_triangle_mesh(mesh_file)
        if not mesh.has_vertices():
            continue
        area = mesh.get_surface_area()
        if area <= 0:
            continue
        num_points = max(int(area * points_per_m2), min_points)
        merged += mesh.sample_points_uniformly(number_of_points=num_points)

    if merged.is_empty():
        raise ValueError(f"Reference cloud sampled from {mesh_dir} is empty.")
    return merged


def preprocess_point_cloud(pcd, voxel_size: float):
    """
    Downsample a cloud and compute FPFH features for global registration.

    Args:
        pcd: Open3D point cloud.
        voxel_size: Voxel size (m) for downsampling; drives feature radii.

    Returns:
        pcd_down: Downsampled cloud with estimated normals.
        pcd_fpfh: FPFH feature for the downsampled cloud.
    """
    if pcd.is_empty():
        raise ValueError(
            "Input point cloud is empty; cannot compute features.")

    pcd_down = pcd.voxel_down_sample(voxel_size)
    if pcd_down.is_empty():
        raise ValueError(
            "Downsampled point cloud is empty; increase input density or lower voxel size.")

    radius_normal = voxel_size * 2
    pcd_down.estimate_normals(
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius_normal, max_nn=30))
    if not pcd_down.has_normals():
        raise ValueError(
            "Failed to estimate normals for point cloud; cannot compute FPFH.")

    radius_feature = voxel_size * 5
    pcd_fpfh = o3d.pipelines.registration.compute_fpfh_feature(
        pcd_down,
        o3d.geometry.KDTreeSearchParamHybrid(radius=radius_feature, max_nn=100))
    return pcd_down, pcd_fpfh


def global_registration(
    source_down, target_down, source_fpfh, target_fpfh, voxel_size: float
):
    """
    Coarse global alignment via RANSAC on FPFH feature matches.

    Args:
        source_down, target_down: Downsampled source/target clouds.
        source_fpfh, target_fpfh: FPFH features for the downsampled clouds.
        voxel_size: Voxel size (m); sets the RANSAC distance threshold.

    Returns:
        Open3D RegistrationResult with the coarse transformation.
    """
    distance_threshold = voxel_size * 1.5
    return o3d.pipelines.registration.registration_ransac_based_on_feature_matching(
        source_down, target_down, source_fpfh, target_fpfh, True, distance_threshold,
        o3d.pipelines.registration.TransformationEstimationPointToPoint(False),
        3,
        [
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnEdgeLength(
                0.9),
            o3d.pipelines.registration.CorrespondenceCheckerBasedOnDistance(
                distance_threshold),
        ],
        o3d.pipelines.registration.RANSACConvergenceCriteria(100000, 0.999),
    )


def refine_registration(
    source,
    target,
    init_transformation,
    scales: list,
    max_iteration: int,
    relative_fitness: float,
    relative_rmse: float,
) -> tuple:
    """
    Coarse-to-fine point-to-plane ICP refinement over decreasing thresholds.

    Args:
        source, target: Full-resolution source/target clouds.
        init_transformation: 4x4 initial transform (e.g. from global registration).
        scales: Decreasing correspondence thresholds (m), coarse to fine.
        max_iteration: Max ICP iterations per scale.
        relative_fitness, relative_rmse: ICP convergence criteria.

    Returns:
        transformation: Final 4x4 transform.
        stages: List of IcpStageMetric, one per scale.
    """
    transformation = init_transformation
    stages = []

    for threshold in scales:
        radius = max(threshold * 2, 0.02)
        search_param = o3d.geometry.KDTreeSearchParamHybrid(
            radius=radius, max_nn=50)
        source.estimate_normals(search_param=search_param)
        target.estimate_normals(search_param=search_param)

        result = o3d.pipelines.registration.registration_icp(
            source, target, threshold, transformation,
            o3d.pipelines.registration.TransformationEstimationPointToPlane(),
            o3d.pipelines.registration.ICPConvergenceCriteria(
                max_iteration=max_iteration,
                relative_fitness=relative_fitness,
                relative_rmse=relative_rmse,
            ),
        )
        transformation = result.transformation
        stages.append(
            IcpStageMetric(
                threshold=threshold,
                fitness=result.fitness,
                inlier_rmse=result.inlier_rmse,
                correspondences=len(result.correspondence_set),
            )
        )

    return transformation, stages
