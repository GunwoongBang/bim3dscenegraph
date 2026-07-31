"""
Point cloud preprocessing (downsampling, outlier removal, cropping) of PCD data.
"""

from pathlib import Path

import numpy as np

from .util import (
    read_point_cloud,
    # voxel_downsample,
    # remove_statistical_outliers,
    floor_removal,
)
from .validation import log_cleaning_validation


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

    input_count = len(np.asarray(cloud.points))
    cleaned_path = floor_removal(pcd_path, cloud, floor_z_cutoff)

    # Stage 0 validation: incoming vs. surviving points after floor removal.
    output_count = len(np.asarray(read_point_cloud(cleaned_path).points))
    log_cleaning_validation(input_count, output_count, logger)

    if logger:
        logger.logText(
            "SCAN2GRAPH", f"Cleaned PCD saved: {cleaned_path} (floor removal)")

    return cleaned_path
