"""
Main orchestrator for SENSOR2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

from pathlib import Path

import ifcopenshell

from .worker import (
    clean_point_cloud,
    segment_point_cloud,
    exclude_points,
)


def sensor2graph(pcd_path, arc_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. If PCD data is missing, export IFC to SDF and generate point cloud (using ifc2pointcloud package)
        3. Segment point cloud using plane detection and IFC geometry
        4. Visualize segmented point cloud with semantic labels

    Args:
        pcd_path: Path to the PCD PCD file
        arc_path: Path to the ARC IFC file
        logger: Optional logger for output messages
    """
    if logger:
        if Path(pcd_path).exists():
            logger.logText("SENSOR2GRAPH", "ARC, PCD IFC models loaded")
        else:
            logger.logText("SENSOR2GRAPH", "ARC IFC model loaded")

    # Load ARC IFC model
    arc_model = ifcopenshell.open(arc_path)

    # =========================================================================
    # Clean & Segment point cloud
    # =========================================================================
    # Point cloud preprocessing
    # Note: Will shortly be reintroduced. For now we assume that we have a clean point cloud
    pcd_path_ = Path("pc_models/cloudGlobal_cc.pcd")
    cleaned_pcd_path = clean_point_cloud(pcd_path_, logger)

    # Point cloud segmentation and labeling
    # Note: Current method is manual segmentation, but will shortly be replaced
    # by an automatic method that combines plane detection with IFC geometry
    segmented_csv_path = segment_point_cloud(
        cleaned_pcd_path,
        arc_model,
        logger,
    )

    excluded_pcd, excluded_csv_path = exclude_points(
        cleaned_pcd_path, Path("cloudGlobal_cc_cleaned_label.csv"), logger)

    # =========================================================================
    # Merge point cloud with BIM-derived graph
    # =========================================================================

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
