"""
Point cloud segmentation.
"""

from pathlib import Path

import open3d as o3d
import numpy as np
import pandas as pd

from .util import (
    InteractiveLabeler,
    create_labeled_cloud,
    extract_plane_groups,
    read_point_cloud,
)


def _make_plane_colors(plane_groups, n_points):
    """Create deterministic colors for plane visualization."""
    colors = np.ones((n_points, 3), dtype=np.float64) * 0.35
    for plane_group in plane_groups:
        segment_id = plane_group["segment_id"]
        rng = np.random.default_rng(1337 + int(segment_id))
        colors[plane_group["inlier_indices"]] = rng.random(3) * 0.6 + 0.25
    return colors


def _pick_seed_point(cloud, colors, window_name="Plane Picker"):
    """Open a selection-capable viewer and return one picked point index."""
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


def _print_ifc_wall_options(walls):
    """Print IFC wall options as numbered menu entries."""
    print("\nAvailable IFC wall labels:")
    for idx, wall in enumerate(walls, start=1):
        wall_name = getattr(wall, "Name", None) or "Unnamed"
        wall_id = getattr(wall, "GlobalId", None) or "NoGlobalId"
        print(f"  {idx}. IfcWall: {wall_id} ({wall_name})")


def segment_point_cloud_by_planes_and_ifc(
    pcd_path,
    ifc_model,
    logger=None,
):
    """Pick a seed point, select its whole plane, then assign IFC wall semantics."""
    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    cloud = read_point_cloud(pcd_path)
    plane_groups, residual_cloud = extract_plane_groups(
        cloud,
        distance_threshold=0.02,
        min_inliers=500,
        max_planes=50,
        num_iterations=1000,
    )

    points = np.asarray(cloud.points)
    n_points = len(points)
    point_to_plane = np.full(n_points, -1, dtype=np.int32)
    plane_by_id = {}
    for plane_group in plane_groups:
        plane_id = int(plane_group["segment_id"])
        plane_by_id[plane_id] = plane_group
        point_to_plane[plane_group["inlier_indices"]] = plane_id

    walls = list(ifc_model.by_type("IfcWall"))
    if not walls:
        raise ValueError("No IfcWall elements were found in the IFC model.")

    output_csv = path.with_name(f"{path.stem}_plane_semantic.csv")

    plane_semantics = {}
    plane_colors = _make_plane_colors(plane_groups, n_points)

    print("\nPlane-based semantic labeling started.")
    print("Pick one point on a plane in the viewer; the whole plane will be selected.")
    print("Press Q to close the viewer after picking the seed point.")

    while True:
        seed_index = _pick_seed_point(
            cloud, plane_colors, window_name="Pick Plane Seed")
        if seed_index is None:
            print("No point picked. Stopping semantic labeling.")
            break

        plane_id = int(point_to_plane[seed_index])
        if plane_id < 0 or plane_id not in plane_by_id:
            print("Picked point does not belong to a detected plane.")
            continue

        plane_group = plane_by_id[plane_id]
        normal = plane_group["normal"]
        point_count = plane_group["point_count"]

        print(
            f"\nSelected plane segment {plane_id} "
            f"(points={point_count}, normal={normal[0]:.3f}, {normal[1]:.3f}, {normal[2]:.3f})"
        )
        _print_ifc_wall_options(walls)

        while True:
            selection = input(
                "Choose IFC wall number, or type 'skip', 'done', or 'list': "
            ).strip().lower()

            if selection in {"done", "quit", "q", "exit"}:
                break
            if selection == "skip":
                break
            if selection == "list":
                _print_ifc_wall_options(walls)
                continue

            if not selection.isdigit():
                print("Enter a valid number, or 'skip', 'done', or 'list'.")
                continue

            wall_index = int(selection) - 1
            if wall_index < 0 or wall_index >= len(walls):
                print("Wall number out of range.")
                continue

            wall = walls[wall_index]
            wall_name = getattr(wall, "Name", None) or "Unnamed"
            wall_id = getattr(wall, "GlobalId", None) or "NoGlobalId"

            plane_semantics[plane_id] = {
                "ifc_type": "IfcWall",
                "ifc_global_id": wall_id,
                "ifc_name": wall_name,
            }
            print(
                f"Assigned plane {plane_id} -> IfcWall: {wall_id} ({wall_name})")
            break

        continue_labeling = input(
            "Label another plane? [Y/n]: ").strip().lower()
        if continue_labeling in {"n", "no", "done", "q", "quit", "exit"}:
            break

    point_indices = np.arange(n_points)
    segment_ids = np.full(n_points, -1, dtype=np.int32)
    surface_types = np.full(n_points, "unlabeled", dtype=object)
    normal_x = np.full(n_points, np.nan, dtype=np.float64)
    normal_y = np.full(n_points, np.nan, dtype=np.float64)
    normal_z = np.full(n_points, np.nan, dtype=np.float64)
    plane_offset = np.full(n_points, np.nan, dtype=np.float64)
    semantic_type = np.full(n_points, "unassigned", dtype=object)
    ifc_type = np.full(n_points, "", dtype=object)
    ifc_global_id = np.full(n_points, "", dtype=object)
    ifc_name = np.full(n_points, "", dtype=object)

    for plane_group in plane_groups:
        plane_id = int(plane_group["segment_id"])
        inlier_indices = plane_group["inlier_indices"]
        normal = plane_group["normal"]
        offset = float(plane_group["plane_model"][3])
        plane_label = f"plane_{plane_id:02d}"

        segment_ids[inlier_indices] = plane_id
        surface_types[inlier_indices] = plane_label
        normal_x[inlier_indices] = normal[0]
        normal_y[inlier_indices] = normal[1]
        normal_z[inlier_indices] = normal[2]
        plane_offset[inlier_indices] = offset

        if plane_id in plane_semantics:
            plane_semantic = plane_semantics[plane_id]
            semantic_type[inlier_indices] = plane_semantic["ifc_type"]
            ifc_type[inlier_indices] = plane_semantic["ifc_type"]
            ifc_global_id[inlier_indices] = plane_semantic["ifc_global_id"]
            ifc_name[inlier_indices] = plane_semantic["ifc_name"]

    df = pd.DataFrame(
        {
            "point_index": point_indices,
            "plane_segment_id": segment_ids,
            "plane_label": surface_types,
            "normal_x": normal_x,
            "normal_y": normal_y,
            "normal_z": normal_z,
            "plane_offset": plane_offset,
            "semantic_type": semantic_type,
            "ifc_type": ifc_type,
            "ifc_global_id": ifc_global_id,
            "ifc_name": ifc_name,
        }
    )
    df.to_csv(output_csv, index=False)

    residual_count = len(np.asarray(residual_cloud.points))
    print(f"Saved plane semantic labels to: {output_csv}")
    print(f"Detected planes: {len(plane_groups)}")
    print(f"Residual unlabeled points: {residual_count}")

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            (
                f"Plane semantic labeling saved: {output_csv} "
                f"(planes={len(plane_groups)}, residual={residual_count})"
            ),
        )

    return output_csv


def segment_point_cloud_interactive(pcd_path, logger=None):
    """
    Interactively segment a point cloud and save labels to CSV.

    Args:
        pcd_path: Path to the cleaned PCD file.
        logger: Optional logger for output messages.

    Returns:
        labels_csv_path: Path to saved labels CSV.
    """
    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    labeler = InteractiveLabeler(pcd_path)

    print("\nInteractive segmentation started.")
    print("Select points in the viewer with Shift + Left Mouse, then press Q to close.")
    print("After closing, enter a surface label in the terminal.")

    while True:
        picked_indices = labeler.pick_points()
        if len(picked_indices) == 0:
            print("No points picked. Stopping interactive segmentation.")
            break

        print(f"Picked {len(picked_indices)} points.")
        surface_type = input(
            "Enter label [floor/ceiling/wall/opening/other] or 'done' to finish: "
        ).strip().lower()

        if surface_type in {"done", "quit", "q", "exit"}:
            break

        labeler.assign_label(surface_type)

        continue_labeling = input(
            "Label another region? [y/N]: "
        ).strip().lower()
        if continue_labeling not in {"y", "yes"}:
            break

    # After segmentation, show summary
    labeler.get_label_counts()

    # Save labels
    labels_csv_path = labeler.save_labels_to_csv()

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Point cloud segmented: {labels_csv_path}")

    return labels_csv_path


def segment_point_cloud_by_planes(
    pcd_path,
    output_csv=None,
    distance_threshold=0.02,
    min_inliers=500,
    max_planes=50,
    num_iterations=1000,
    logger=None,
):
    """Segment a point cloud into planar groups with shared normals."""
    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    cloud = read_point_cloud(pcd_path)
    plane_groups, residual_cloud = extract_plane_groups(
        cloud,
        distance_threshold=distance_threshold,
        min_inliers=min_inliers,
        max_planes=max_planes,
        num_iterations=num_iterations,
    )

    points = np.asarray(cloud.points)
    n_points = len(points)

    if output_csv is None:
        output_csv = path.with_name(f"{path.stem}_planes.csv")
    else:
        output_csv = Path(output_csv)

    point_indices = np.arange(n_points)
    segment_ids = np.full(n_points, -1, dtype=np.int32)
    surface_types = np.full(n_points, "unlabeled", dtype=object)
    normal_x = np.full(n_points, np.nan, dtype=np.float64)
    normal_y = np.full(n_points, np.nan, dtype=np.float64)
    normal_z = np.full(n_points, np.nan, dtype=np.float64)
    plane_offset = np.full(n_points, np.nan, dtype=np.float64)

    for plane_group in plane_groups:
        segment_id = plane_group["segment_id"]
        plane_label = f"plane_{segment_id:02d}"
        inlier_indices = plane_group["inlier_indices"]
        normal = plane_group["normal"]
        offset = float(plane_group["plane_model"][3])

        segment_ids[inlier_indices] = segment_id
        surface_types[inlier_indices] = plane_label
        normal_x[inlier_indices] = normal[0]
        normal_y[inlier_indices] = normal[1]
        normal_z[inlier_indices] = normal[2]
        plane_offset[inlier_indices] = offset

    df = pd.DataFrame(
        {
            "point_index": point_indices,
            "segment_id": segment_ids,
            "surface_type": surface_types,
            "normal_x": normal_x,
            "normal_y": normal_y,
            "normal_z": normal_z,
            "plane_offset": plane_offset,
        }
    )
    df.to_csv(output_csv, index=False)

    residual_count = len(np.asarray(residual_cloud.points))
    print(f"Saved plane segmentation to: {output_csv}")
    print(f"Detected planes: {len(plane_groups)}")
    print(f"Residual unlabeled points: {residual_count}")

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            (
                f"Plane segmentation saved: {output_csv} "
                f"(planes={len(plane_groups)}, residual={residual_count})"
            ),
        )

    return output_csv


def segment_point_cloud_by_ranges(pcd_path, ranges_dict, output_csv=None, logger=None):
    """
    Segment point cloud using coordinate ranges (non-interactive).

    Args:
        pcd_path: Path to the cleaned PCD file.
        ranges_dict: Dict mapping surface_type to coordinate constraints.
        output_csv: Optional custom output CSV path.
        logger: Optional logger for output messages.

    Returns:
        labels_csv_path: Path to saved labels CSV.

    Example:
        ranges = {
            'floor': {'z_max': 0.15},
            'ceiling': {'z_min': 2.8},
            'wall': {'z_min': 0.15, 'z_max': 2.8}
        }
        segment_point_cloud_by_ranges("cloud.pcd", ranges)
    """
    path = Path(pcd_path)
    if not path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {path}")

    labeler = InteractiveLabeler(pcd_path, output_csv_path=output_csv)
    labeler.manual_label_by_range(ranges_dict)
    labeler.get_label_counts()
    labels_csv_path = labeler.save_labels_to_csv()

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Point cloud segmented by ranges: {labels_csv_path}")

    return labels_csv_path


def visualize_labeled_cloud(pcd_path, labels_csv_path, logger=None):
    """
    Load labels and visualize colored point cloud.

    Args:
        pcd_path: Path to the PCD file.
        labels_csv_path: Path to the labels CSV file.
        logger: Optional logger for output messages.
    """
    try:
        import pandas as pd
    except ImportError:
        raise ImportError(
            "pandas is required. Install with: pip install pandas")

    labels_df = pd.read_csv(labels_csv_path)
    cloud = create_labeled_cloud(pcd_path, labels_df)

    if logger:
        logger.logText("SENSOR2GRAPH", f"Labeled cloud visualized")

    import open3d as o3d
    o3d.visualization.draw_geometries([cloud])
