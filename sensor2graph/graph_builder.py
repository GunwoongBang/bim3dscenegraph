"""
Main orchestrator for Sensor-to-Graph conversion.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import ifcopenshell

from .extractor import export_point_cloud, generate_point_cloud, visualize_point_cloud

# from .query_manager import QueryManager
# from .persistence import Neo4jOperations


def sensor2graph(driver, pcd_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract point cloud from point cloud IFC model
        3.

    Args:
        driver: Neo4j driver instance
        pcd_path: Path to the PCD IFC file
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText(
            "SENSOR2GRAPH", "Starting point cloud generation from IFC")

    # Initialize components
    # query_manager = QueryManager()
    # neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    # =========================================================================
    # Generate point cloud from IFC (If XYZ not available)
    # =========================================================================
    # TODO: Need to be refactored to keep the graph_builder clean

    point_cloud = generate_point_cloud(
        model,
        element_types=["IfcWall", "IfcSlab"],
        points_per_m2=200,
        translation=(2, 5, 3),
        yaw_degrees=25,
        logger=logger
    )

    visualize_point_cloud(point_cloud)
    export_point_cloud(pcd_path, point_cloud, logger)
    # =========================================================================
    # Extract data from XYZ
    # =========================================================================

    # =========================================================================
    # Persist to Neo4j
    # =========================================================================

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
