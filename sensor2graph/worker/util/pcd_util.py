"""Point-cloud utility functions for SENSOR2GRAPH."""

from pathlib import Path

import numpy as np

from ..geometry import extract_mesh_from_shape

try:
	import open3d as o3d
except ImportError:  # pragma: no cover - runtime dependency guard
	o3d = None


def ensure_open3d_available():
	"""Raise a clear error if Open3D is not installed."""
	if o3d is None:
		raise RuntimeError(
			"Open3D is required for point-cloud preprocessing. "
			"Install it with: pip install open3d"
		)


def read_point_cloud(pcd_path):
	"""Load a point cloud from a PCD file using Open3D."""
	ensure_open3d_available()

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


def keep_points_inside_ifc_bounds(cloud, bounds, xy_margin, z_margin):
	"""Keep only points inside IFC-derived axis-aligned bounds with margin."""
	if bounds is None:
		return cloud

	points = np.asarray(cloud.points)
	if points.size == 0:
		return cloud

	mask = (
		(points[:, 0] >= bounds["min_x"] - xy_margin)
		& (points[:, 0] <= bounds["max_x"] + xy_margin)
		& (points[:, 1] >= bounds["min_y"] - xy_margin)
		& (points[:, 1] <= bounds["max_y"] + xy_margin)
		& (points[:, 2] >= bounds["min_z"] - z_margin)
		& (points[:, 2] <= bounds["max_z"] + z_margin)
	)

	kept_indices = np.where(mask)[0].tolist()
	if not kept_indices:
		return cloud

	return cloud.select_by_index(kept_indices)


def write_point_cloud(cloud, input_path, suffix="_cleaned"):
	"""Write a cleaned cloud to {stem}{suffix}{ext} and return its path."""
	ensure_open3d_available()

	src = Path(input_path)
	output_path = src.with_name(f"{src.stem}{suffix}{src.suffix}")
	o3d.io.write_point_cloud(str(output_path), cloud, write_ascii=True)
	return output_path


def count_points(cloud):
	"""Return point count for an Open3D point cloud."""
	return len(np.asarray(cloud.points))
