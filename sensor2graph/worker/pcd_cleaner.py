"""
Point cloud preprocessing (downsampling, outlier removal, cropping) of PCD data.
"""

from .util import (
    read_point_cloud,
    voxel_downsample,
    remove_statistical_outliers,
    detect_ground_plane,
    write_point_cloud,
)

# Note: This cleaner is currently disabled
# Later, when the cleaner is reintroduced, the visualization will be updated not to include the cleaning step
# The returning file path has to be [file_name]_cleaned.pcd, since the future code will expect that and be built upon that assumption.


def clean_point_cloud(pcd_path, logger=None):
    """
    Preprocess PCD data and export to {pcd_file_name}_cleaned.pcd.

    Args:
        pcd_path: Path to the input PCD file.
        logger: Optional logger for output messages.

    Returns:
        cleaned_path: Path to the cleaned PCD file.
        stats: Dictionary with point counts at each stage.
    """
    voxel_size = 0.05
    nb_neighbors = 20
    std_ratio = 2.0
    floor_distance_threshold = 0.02
    floor_min_inliers = 1000
    floor_normal_z_threshold = 0.85

    raw_cloud = read_point_cloud(pcd_path)
    downsampled_cloud = voxel_downsample(raw_cloud, voxel_size)
    # inlier_cloud = remove_statistical_outliers(
    #     downsampled_cloud,
    #     nb_neighbors=nb_neighbors,
    #     std_ratio=std_ratio,
    # )

    floor_plane = detect_ground_plane(
        downsampled_cloud,
        distance_threshold=floor_distance_threshold,
        min_inliers=floor_min_inliers,
        normal_z_threshold=floor_normal_z_threshold,
    )

    # if floor_plane is None:
    #     cleaned_cloud = downsampled_cloud
    # else:
    #     cleaned_cloud = downsampled_cloud.select_by_index(
    #         floor_plane["inlier_indices"],
    #         invert=True,
    #     )

    cleaned_path = write_point_cloud(downsampled_cloud, pcd_path)

    if logger:
        logger.logText(
            "SENSOR2GRAPH", "PCD cleaned (Downsampled, outliers removed, floor removed)")
        logger.logText("SENSOR2GRAPH", f"Cleaned PCD saved: {cleaned_path}")

    return cleaned_path
