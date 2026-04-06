"""Standalone point-cloud visualizer with CSV-driven categories."""

from __future__ import annotations

from pathlib import Path
import argparse

import numpy as np
import pandas as pd
import open3d as o3d


COMMON_CATEGORY_COLS = (
    "ifc_global_id",
    "semantic_type",
    "ifc_type",
    "surface_type",
    "plane_label",
    "category",
    "label",
)

COMMON_COLORS = {
}


def _infer_category_column(labels_df, requested_column=None):
    """Pick a category column from the CSV."""
    if requested_column:
        if requested_column not in labels_df.columns:
            raise ValueError(
                f"Category column '{requested_column}' was not found in the CSV."
            )
        return requested_column

    for column in COMMON_CATEGORY_COLS:
        if column in labels_df.columns:
            return column

    raise ValueError(
        "Could not infer a category column. "
        f"Expected one of: {', '.join(COMMON_CATEGORY_COLS)}"
    )


def _build_color_for_category(category, cache):
    """Create a deterministic color for arbitrary categories."""
    if category not in cache:
        seed = abs(hash(category)) % (2**32)
        rng = np.random.default_rng(seed)
        cache[category] = rng.random(3) * 0.6 + 0.2
    return cache[category]


def visualize_point_cloud_with_categories(
    pcd_path,
    csv_path,
    category_column=None,
    point_index_column="point_index",
    logger=None,
):
    """Visualize a point cloud colored by categories stored in a CSV file."""
    pcd_path = Path(pcd_path)
    csv_path = Path(csv_path)

    if not pcd_path.exists():
        raise FileNotFoundError(f"Point cloud file not found: {pcd_path}")
    if not csv_path.exists():
        raise FileNotFoundError(f"CSV file not found: {csv_path}")

    cloud = o3d.io.read_point_cloud(str(pcd_path))
    points = np.asarray(cloud.points)
    if points.size == 0:
        raise ValueError(f"No points found in point cloud: {pcd_path}")

    labels_df = pd.read_csv(csv_path)

    if "ifc_type" not in labels_df.columns:
        raise ValueError(
            "CSV must contain an 'ifc_type' column to filter IFC walls.")
    if "ifc_global_id" not in labels_df.columns:
        raise ValueError(
            "CSV must contain an 'ifc_global_id' column for IFC wall coloring.")

    wall_rows = labels_df[
        labels_df["ifc_type"].astype(str).str.strip().eq("IfcWall")
        & labels_df["ifc_global_id"].notna()
        & labels_df["ifc_global_id"].astype(str).str.strip().ne("")
    ].copy()

    if "semantic_type" in wall_rows.columns:
        wall_rows = wall_rows[
            wall_rows["semantic_type"].astype(
                str).str.strip().str.lower().ne("unassigned")
        ].copy()

    if wall_rows.empty:
        raise ValueError("No IFC wall points were found in the CSV.")

    category_column = "ifc_global_id"

    colors = np.ones((len(points), 3), dtype=np.float64) * 0.55
    category_color_cache = {}
    used_categories = set()

    for row_idx, row in wall_rows.iterrows():
        point_idx = int(
            row[point_index_column]) if point_index_column in wall_rows.columns else int(row_idx)
        if point_idx < 0 or point_idx >= len(points):
            continue

        raw_value = row.get(category_column, None)
        if pd.isna(raw_value):
            continue

        category = str(raw_value).strip()
        if not category or category.lower() in {"", "nan", "none", "unlabeled", "unassigned"}:
            continue

        used_categories.add(category)
        colors[point_idx] = _build_color_for_category(
            category, category_color_cache)

    cloud.colors = o3d.utility.Vector3dVector(colors)

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            f"Visualizing categories from {csv_path.name} using column '{category_column}'",
        )

    print(f"Point cloud: {pcd_path}")
    print(f"CSV labels: {csv_path}")
    print(f"Category column: {category_column}")
    print(f"Filtered rows: {len(wall_rows)} IfcWall points")
    print("\nCategory legend:")
    for category in sorted(used_categories):
        color = _build_color_for_category(category, category_color_cache)
        color_text = ", ".join(f"{c:.2f}" for c in color)
        print(f"  {category}: [{color_text}]")

    o3d.visualization.draw_geometries([cloud])
    return cloud


def _build_arg_parser():
    parser = argparse.ArgumentParser(
        description="Visualize a point cloud colored by semantic labels stored in a CSV file."
    )
    parser.add_argument(
        "pcd_path",
        nargs="?",
        default="pc_models/cloudGlobal_cleaned.pcd",
        help="Path to the PCD file.",
    )
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="pc_models/cloudGlobal_cleaned_plane_semantic.csv",
        help="Path to the CSV file containing labels.",
    )
    parser.add_argument(
        "--category-column",
        dest="category_column",
        default=None,
        help="CSV column name to use as the category. If omitted, it will be inferred.",
    )
    parser.add_argument(
        "--point-index-column",
        dest="point_index_column",
        default="point_index",
        help="CSV column that stores the point index.",
    )
    return parser


if __name__ == "__main__":
    args = _build_arg_parser().parse_args()
    visualize_point_cloud_with_categories(
        args.pcd_path,
        args.csv_path,
        category_column=args.category_column,
        point_index_column=args.point_index_column,
    )
