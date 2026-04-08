"""
Point cloud preprocessing (downsampling, outlier removal, cropping) of PCD data.
"""

from .util import (
    read_point_cloud,
    voxel_downsample,
    remove_statistical_outliers,
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
    """
    voxel_size = 0.05
    nb_neighbors = 20
    std_ratio = 2.0
    floor_z_cutoff = -0.55

    cloud = read_point_cloud(pcd_path)
    # downsampled_cloud = voxel_downsample(cloud, voxel_size)
    # inlier_cloud = remove_statistical_outliers(
    #     downsampled_cloud,
    #     nb_neighbors = nb_neighbors,
    #     std_ratio = std_ratio,
    # )

    points = cloud.points
    keep_indices = [idx for idx, point in enumerate(
        points) if point[2] > floor_z_cutoff]
    cleaned_cloud = cloud.select_by_index(keep_indices)

    cleaned_path = write_point_cloud(cleaned_cloud, pcd_path)

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"PCD cleaned (Downsampled, outliers removed, z <= {floor_z_cutoff}m removed)")
        logger.logText("SENSOR2GRAPH", f"Cleaned PCD saved: {cleaned_path}")

    return cleaned_path
