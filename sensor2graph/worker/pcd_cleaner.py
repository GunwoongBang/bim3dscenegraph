"""
Point cloud preprocessing (downsampling, outlier removal, cropping) of PCD data.
"""

from pathlib import Path


from .util import (
    read_point_cloud,
    # voxel_downsample,
    # remove_statistical_outliers,
    floor_removal,
)


# Later, when the cleaner is reintroduced, the visualization will be updated not to include the cleaning step
# The returning file path has to be [file_name]_cleaned.pcd, since the future code will expect that and be built upon that assumption.

def clean_point_cloud(pcd_path: Path, logger=None) -> Path:
    """
    Preprocess PCD data and export to {pcd_file_name}_cleaned.pcd.

    Args:
        pcd_path: Path to the input PCD file.
        logger: Optional logger for output messages.

    Returns:
        cleaned_path: Path to the cleaned PCD file.
    """
    # voxel_size = 0.05
    # nb_neighbors = 20
    # std_ratio = 2.0
    floor_z_cutoff = -0.555

    cloud = read_point_cloud(pcd_path)
    # downsampled_cloud = voxel_downsample(cloud, voxel_size)
    # inlier_cloud = remove_statistical_outliers(
    #     downsampled_cloud,
    #     nb_neighbors = nb_neighbors,
    #     std_ratio = std_ratio,
    # )

    cleaned_path = floor_removal(pcd_path, cloud, floor_z_cutoff)

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Cleaned PCD saved: {cleaned_path} (floor removal)")

    return cleaned_path
