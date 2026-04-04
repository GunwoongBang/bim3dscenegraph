"""
Point cloud segmentation.
"""

from pathlib import Path

from .util import InteractiveLabeler, create_labeled_cloud


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
