"""
Point cloud preprocessing (downsampling, outlier removal, cropping) of PCD data.
"""

from .util import (
    read_point_cloud,
    voxel_downsample,
    remove_statistical_outliers,
    compute_ifc_bounds,
    keep_points_inside_ifc_bounds,
    write_point_cloud,
    count_points,
)

# Note: This cleaner is currently disabled
# Later, when the cleaner is reintroduced, the visualization will be updated not to include the cleaning step
# The returning file path has to be [file_name]_cleaned.pcd, since the future code will expect that and be built upon that assumption.


def clean_point_cloud(pcd_path, arc_model, logger=None):
    """
    Preprocess PCD data and export to {pcd_file_name}_cleaned.pcd.

    Args:
        pcd_path: Path to the input PCD file.
        arc_model: ARC IFC model for computing bounds.
        logger: Optional logger for output messages.

    Returns:
        cleaned_path: Path to the cleaned PCD file.
        stats: Dictionary with point counts at each stage.
    """
    voxel_size = 0.05
    nb_neighbors = 20
    std_ratio = 2.0
    margin = 0.50

    raw_cloud = read_point_cloud(pcd_path)
    downsampled_cloud = voxel_downsample(raw_cloud, voxel_size)
    inlier_cloud = remove_statistical_outliers(
        downsampled_cloud,
        nb_neighbors=nb_neighbors,
        std_ratio=std_ratio,
    )

    ifc_bounds = compute_ifc_bounds(arc_model)
    cleaned_cloud = keep_points_inside_ifc_bounds(
        inlier_cloud,
        bounds=ifc_bounds,
        margin=margin,
    )

    cleaned_path = write_point_cloud(cleaned_cloud, pcd_path)
    stats = {
        "raw": count_points(raw_cloud),
        "downsampled": count_points(downsampled_cloud),
        "inlier": count_points(inlier_cloud),
        "cleaned": count_points(cleaned_cloud),
        "output": str(cleaned_path),
    }

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            (
                "PCD cleaned "
                f"(raw={stats['raw']}, downsampled={stats['downsampled']}, "
                f"inlier={stats['inlier']}, cleaned={stats['cleaned']})"
            ),
        )
        logger.logText("SENSOR2GRAPH", f"Cleaned PCD saved: {cleaned_path}")

    return cleaned_path
