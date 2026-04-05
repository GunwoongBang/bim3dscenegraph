"""
Main orchestrator for SENSOR2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

from pathlib import Path

import ifcopenshell

from .worker import (
    export_ifc_to_sdf,
    segment_point_cloud_interactive,
    segment_point_cloud_by_planes,
    segment_point_cloud_by_planes_and_ifc,
    visualize_labeled_cloud,
)


def sensor2graph(pcd_path, arc_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract point cloud from point cloud IFC model
        3. Reconstruct surface mesh from point cloud

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
    # Generate point cloud as fallback if PCD data is not present
    # =========================================================================
    # Export IFC to SDF
    if not Path(pcd_path).exists():
        if logger:
            logger.logText(
                "SENSOR2GRAPH", "Point cloud file not found. Exporting IFC to SDF as fallback.")

        export_ifc_to_sdf(arc_model, logger)
        pcd_path = Path("pc_models/cloudGlobal.pcd")

    # =========================================================================
    # Segment point cloud
    # =========================================================================
    # Point cloud preprocessing
    # Note: Will shortly be reintroduced. For now we assume that we have a clean point cloud
    cleaned_pcd_path = Path("pc_models/cloudGlobal_cleaned.pcd")

    # Point cloud segmentation and labeling
    # segment_point_cloud_interactive(cleaned_pcd_path, logger)
    plane_semantic_csv = segment_point_cloud_by_planes_and_ifc(
        cleaned_pcd_path,
        arc_model,
        logger=logger,
    )
    visualize_labeled_cloud(cleaned_pcd_path, plane_semantic_csv, logger)

    # =========================================================================
    # Merge point cloud with BIM-derived graph
    # =========================================================================

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
