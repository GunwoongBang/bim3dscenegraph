"""
Standalone point-cloud reconstruction pipeline.

This module reconstructs a surface mesh directly from scanned point cloud data
(e.g., LAZ/LAS). It is intentionally decoupled from IFC-based point cloud
generation so it can be used with real scans.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import argparse

import laspy
import numpy as np
import open3d as o3d


@dataclass
class PoissonConfig:
    """Configuration for Poisson reconstruction pipeline."""

    # Pre-processing
    voxel_size: float | None = None
    outlier_nb_neighbors: int = 20
    outlier_std_ratio: float = 2.0

    # Normal estimation
    normal_radius_multiplier: float = 2.5
    normal_max_nn: int = 30
    orient_k: int = 30

    # Poisson reconstruction
    poisson_depth: int = 10
    poisson_scale: float = 1.1
    poisson_linear_fit: bool = False

    # Post-processing
    density_quantile_to_remove: float = 0.02
    taubin_iterations: int = 5
    simplify_target_triangles: int | None = None


def _log(logger, message: str) -> None:
    if logger is None:
        return
    if hasattr(logger, "logText"):
        logger.logText("RECONSTRUCTION", message)
    else:
        logger(message)


def load_laz_as_point_cloud(laz_path: str | Path) -> o3d.geometry.PointCloud:
    """Load a LAZ/LAS file into an Open3D point cloud."""
    las = laspy.read(str(laz_path))

    points = np.column_stack((las.x, las.y, las.z)).astype(np.float64)
    if points.size == 0:
        raise ValueError(f"No points found in {laz_path}")

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(points)

    dim_names = set(las.point_format.dimension_names)
    if {"red", "green", "blue"}.issubset(dim_names):
        colors = np.column_stack(
            (las.red, las.green, las.blue)).astype(np.float64)
        max_color = np.max(colors)
        if max_color > 0:
            colors = colors / max_color
            colors = np.clip(colors, 0.0, 1.0)
            pcd.colors = o3d.utility.Vector3dVector(colors)

    return pcd


def _auto_voxel_size(pcd: o3d.geometry.PointCloud) -> float:
    """
    Heuristic voxel size from bounding-box diagonal.

    Uses 0.2% of diagonal as a practical starting point.
    """
    bbox = pcd.get_axis_aligned_bounding_box()
    diagonal = np.linalg.norm(np.asarray(bbox.get_extent()))
    return max(diagonal * 0.002, 1e-4)


def preprocess_point_cloud(
        pcd: o3d.geometry.PointCloud,
        cfg: PoissonConfig,
) -> tuple[o3d.geometry.PointCloud, float]:
    """Downsample and denoise point cloud before reconstruction."""
    voxel_size = cfg.voxel_size if cfg.voxel_size is not None else _auto_voxel_size(
        pcd)

    pcd = pcd.voxel_down_sample(voxel_size)
    pcd, _ = pcd.remove_statistical_outlier(
        nb_neighbors=cfg.outlier_nb_neighbors,
        std_ratio=cfg.outlier_std_ratio,
    )
    if len(pcd.points) == 0:
        raise ValueError("All points were removed during pre-processing")

    return pcd, voxel_size


def estimate_normals(
        pcd: o3d.geometry.PointCloud,
        voxel_size: float,
        cfg: PoissonConfig,
) -> o3d.geometry.PointCloud:
    """Estimate and orient normals for Poisson reconstruction."""
    radius = voxel_size * cfg.normal_radius_multiplier

    pcd.estimate_normals(
        search_param=o3d.geometry.KDTreeSearchParamHybrid(
            radius=radius,
            max_nn=cfg.normal_max_nn,
        )
    )
    pcd.orient_normals_consistent_tangent_plane(cfg.orient_k)
    return pcd


def poisson_reconstruct(
        pcd: o3d.geometry.PointCloud,
        cfg: PoissonConfig,
) -> o3d.geometry.TriangleMesh:
    """Run Poisson reconstruction and basic mesh cleanup."""
    mesh, densities = o3d.geometry.TriangleMesh.create_from_point_cloud_poisson(
        pcd,
        depth=cfg.poisson_depth,
        scale=cfg.poisson_scale,
        linear_fit=cfg.poisson_linear_fit,
    )

    if len(mesh.vertices) == 0:
        raise ValueError("Poisson produced an empty mesh")

    # Remove low-density vertices, which often correspond to unstable regions.
    density_arr = np.asarray(densities)
    if len(density_arr) != len(mesh.vertices):
        raise ValueError(
            "Poisson density output is inconsistent with mesh vertices "
            f"(densities={len(density_arr)}, vertices={len(mesh.vertices)})"
        )
    threshold = np.quantile(density_arr, cfg.density_quantile_to_remove)
    low_density_mask = density_arr < threshold
    mesh.remove_vertices_by_mask(low_density_mask)

    # Keep geometry inside scan bounds to reduce Poisson extrapolation artifacts.
    bbox = pcd.get_axis_aligned_bounding_box()
    mesh = mesh.crop(bbox)

    if len(mesh.vertices) == 0:
        raise ValueError("Poisson produced an empty mesh after cropping")

    mesh.remove_degenerate_triangles()
    mesh.remove_duplicated_triangles()
    mesh.remove_duplicated_vertices()
    mesh.remove_non_manifold_edges()

    if cfg.taubin_iterations > 0:
        mesh = mesh.filter_smooth_taubin(
            number_of_iterations=cfg.taubin_iterations)

    if cfg.simplify_target_triangles:
        mesh = mesh.simplify_quadric_decimation(cfg.simplify_target_triangles)

    mesh.compute_vertex_normals()
    return mesh


def reconstruct_poisson_from_laz(
        laz_path: str | Path,
        output_mesh_path: str | Path,
        cfg: PoissonConfig | None = None,
        logger=None,
) -> dict:
    """
    End-to-end Poisson reconstruction from a LAZ/LAS point cloud.

    Returns basic reconstruction statistics.
    """
    cfg = cfg or PoissonConfig()
    laz_path = Path(laz_path)
    output_mesh_path = Path(output_mesh_path)

    _log(logger, f"Loading point cloud: {laz_path}")
    raw_pcd = load_laz_as_point_cloud(laz_path)
    raw_points = len(raw_pcd.points)
    _log(logger, f"Loaded {raw_points} points")

    _log(logger, "Pre-processing point cloud")
    pcd, voxel_size = preprocess_point_cloud(raw_pcd, cfg)
    _log(
        logger, f"After pre-processing: {len(pcd.points)} points (voxel={voxel_size:.6f})")

    _log(logger, "Estimating normals")
    pcd = estimate_normals(pcd, voxel_size, cfg)

    _log(logger, "Running Poisson reconstruction")
    mesh = poisson_reconstruct(pcd, cfg)

    output_mesh_path.parent.mkdir(parents=True, exist_ok=True)
    ok = o3d.io.write_triangle_mesh(str(output_mesh_path), mesh)
    if not ok:
        raise RuntimeError(f"Failed to write mesh to {output_mesh_path}")

    _log(
        logger,
        f"Mesh exported to {output_mesh_path} "
        f"(vertices={len(mesh.vertices)}, triangles={len(mesh.triangles)})",
    )

    return {
        "input_points": raw_points,
        "processed_points": len(pcd.points),
        "mesh_vertices": len(mesh.vertices),
        "mesh_triangles": len(mesh.triangles),
        "voxel_size": voxel_size,
        "output_mesh": str(output_mesh_path),
    }


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Poisson reconstruction from LAZ/LAS")
    parser.add_argument("--input", required=True,
                        help="Input LAZ/LAS file path")
    parser.add_argument("--output", required=True,
                        help="Output mesh path (.ply/.obj/.stl)")
    parser.add_argument("--depth", type=int, default=10,
                        help="Poisson octree depth")
    parser.add_argument("--voxel", type=float, default=None,
                        help="Voxel size for downsampling")
    parser.add_argument("--simplify", type=int, default=None,
                        help="Target triangle count")
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    config = PoissonConfig(
        poisson_depth=args.depth,
        voxel_size=args.voxel,
        simplify_target_triangles=args.simplify,
    )

    stats = reconstruct_poisson_from_laz(args.input, args.output, config)
    print("Reconstruction complete")
    for k, v in stats.items():
        print(f"{k}: {v}")
