"""
Main orchestrator for SENSOR2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import ifcopenshell

from .worker import (
    export_ifc_to_sdf,
    visualize_point_cloud,
)


def sensor2graph(pcd_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract point cloud from point cloud IFC model
        3. Reconstruct surface mesh from point cloud

    Args:
        pcd_path: Path to the PCD IFC file
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText("SENSOR2GRAPH", "PCD IFC model loaded")

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    # =========================================================================
    # Generate SDF model from IFC
    # =========================================================================
    export_ifc_to_sdf(model, logger)

    # =========================================================================
    # Extract data from point cloud
    # =========================================================================
    pc_path = "pc_models/cloudGlobal.pcd"
    visualize_point_cloud(pc_path)

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
