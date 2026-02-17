"""
Main orchestrator for Sensor-to-Graph conversion.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import os
import open3d as o3d
import ifcopenshell

from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .extractor import (
    generate_point_cloud,
)


def sensor2graph(driver, pcd_path=None, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

     This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract geometry (point cloud) from architectural elements
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
    query_manager = QueryManager()
    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    # =========================================================================
    # Generate point cloud from IFC (If XYZ not available)
    # =========================================================================
    # TODO: Need to be refactored to keep the graph_builder clean

    if (pcd_path is not None):
        point_cloud = generate_point_cloud(
            model,
            element_types=["IfcWall", "IfcSlab"],
            points_per_m2=100,  # Adjust density as needed
            translation=(2, 5, 3),  # x: 2m, y: 5m, z: 3m
            yaw_degrees=25,  # 25 degree rotation around Z-axis
            logger=logger
        )

        # Visualize the point cloud with colors
        coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=1.0)

        o3d.visualization.draw_geometries(
            [point_cloud, coord_frame],
            window_name="Point Cloud from IFC (transformed)",
            width=1200,
            height=800
        )

        # Export the point cloud data to a xyz file
        model_name = os.path.splitext(os.path.basename(pcd_path))[0]
        o3d.io.write_point_cloud(f"pc_models/{model_name}.xyz", point_cloud)
        print(model_name)

        if logger:
            logger.logText(
                "SENSOR2GRAPH", f"Point cloud exported to pc_models/{model_name}.xyz")

    # =========================================================================
    # Extract data from XYZ
    # =========================================================================

    # =========================================================================
    # Persist to Neo4j
    # =========================================================================

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
