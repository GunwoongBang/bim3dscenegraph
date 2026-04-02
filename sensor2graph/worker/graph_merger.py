"""

"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def _read_ascii_pcd_xyz(pc_path) -> np.ndarray:
    """Load XYZ coordinates from an ASCII PCD file."""
    with pc_path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()

    data_line_index = -1
    for idx, line in enumerate(lines):
        if line.strip().upper().startswith("DATA"):
            data_line_index = idx
            break

    if data_line_index < 0:
        raise ValueError("Invalid PCD: missing DATA section.")

    data_mode = lines[data_line_index].strip().split(maxsplit=1)[-1].lower()
    if data_mode != "ascii":
        raise ValueError(
            f"Unsupported PCD DATA mode '{data_mode}'. Only ASCII is supported."
        )

    points = []
    for line in lines[data_line_index + 1:]:
        raw = line.strip()
        if not raw:
            continue
        parts = raw.split()
        if len(parts) < 3:
            continue
        points.append((float(parts[0]), float(parts[1]), float(parts[2])))

    if not points:
        raise ValueError("No points found in PCD data section.")

    return np.asarray(points, dtype=np.float32)


def _voxel_downsample(points, voxel_size) -> np.ndarray:
    """Downsample points by averaging coordinates within each voxel."""
    if voxel_size <= 0:
        return points

    min_corner = points.min(axis=0)
    voxel_indices = np.floor((points - min_corner) /
                             voxel_size).astype(np.int64)

    unique_voxels, inverse = np.unique(
        voxel_indices, axis=0, return_inverse=True)
    downsampled = np.zeros((len(unique_voxels), 3), dtype=np.float32)

    for idx in range(len(unique_voxels)):
        members = points[inverse == idx]
        downsampled[idx] = members.mean(axis=0)

    return downsampled


def _remove_sparse_noise(points, neighborhood_voxel, min_neighbors) -> np.ndarray:
    """Remove isolated points using occupied-voxel neighborhood density."""
    if neighborhood_voxel <= 0 or min_neighbors <= 0:
        return points

    min_corner = points.min(axis=0)
    voxels = np.floor((points - min_corner) /
                      neighborhood_voxel).astype(np.int64)
    unique_voxels, inverse = np.unique(voxels, axis=0, return_inverse=True)

    occupied = {tuple(v): idx for idx, v in enumerate(unique_voxels)}
    keep_voxel = np.zeros(len(unique_voxels), dtype=bool)

    offsets = [
        (dx, dy, dz)
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
        for dz in (-1, 0, 1)
        if not (dx == 0 and dy == 0 and dz == 0)
    ]

    for idx, voxel in enumerate(unique_voxels):
        vx, vy, vz = voxel
        neighbor_count = 0
        for dx, dy, dz in offsets:
            if (vx + dx, vy + dy, vz + dz) in occupied:
                neighbor_count += 1
        if neighbor_count >= min_neighbors:
            keep_voxel[idx] = True

    keep_mask = keep_voxel[inverse]
    filtered = points[keep_mask]
    return filtered if len(filtered) > 0 else points


def visualize_point_cloud(pc_path, logger=None):
    """
    Visualize a PCD point cloud with Matplotlib.

    Args:
        pc_path: Path to a .pcd file.
        logger: Optional logger for output messages.
    """
    if not Path(pc_path).exists():
        raise FileNotFoundError(f"Point cloud file not found: {pc_path}")

    voxel_size = 0.07
    noise_voxel_size = 0.06
    min_neighbors = 2

    raw_points = _read_ascii_pcd_xyz(pc_path)
    downsampled_points = _voxel_downsample(raw_points, voxel_size)
    points_to_show = _remove_sparse_noise(
        downsampled_points, noise_voxel_size, min_neighbors)

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Point-cloud preprocessing (raw={len(raw_points)}, downsampled={len(downsampled_points)} denoised={len(points_to_show)})")

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
    ax.set_title(f"Point Cloud Viewer: {pc_path.name}")
    ax.set_xlabel("X")
    ax.set_ylabel("Y")
    ax.set_zlabel("Z")

    mins = points_to_show.min(axis=0)
    maxs = points_to_show.max(axis=0)
    centers = (mins + maxs) / 8.0
    half_range = (maxs - mins).max() / 8.0

    ax.set_xlim(centers[0] - half_range, centers[0] + half_range)
    ax.set_ylim(centers[1] - half_range, centers[1] + half_range)
    ax.set_zlim(centers[2] - half_range, centers[2] + half_range)
    ax.set_box_aspect((1, 1, 1))

    plt.tight_layout()
    plt.show()
