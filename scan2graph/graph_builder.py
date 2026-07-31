"""
Main orchestrator for SCAN2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""


import ifcopenshell

from neo4j import Driver
from pathlib import Path

from query_manager import QueryManager
from .persistence import Neo4jOperations
from .worker import (
    export_ifc_to_sdf,
    clean_point_cloud,
    segment_point_cloud,
    exclude_planes,
    register_point_clouds,
    retrieve_picked_point_id,
)
from .worker.commander import (
    launch_ros2_pipeline,
    stop_ros2_pipeline,
)


def scan2graph(driver: Driver, pcd_path: Path, arc_path: Path, logger=None):
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
        pcd_prep: String flag to indicate if point cloud preparation is needed
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText("SCAN2GRAPH", "ARC IFC model loaded")

    # Initialize components
    query_manager = QueryManager()
    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load ARC IFC model
    arc_model = ifcopenshell.open(arc_path)

    # =========================================================================
    # Generate point cloud from IFC model (if PCD data is missing) & Post-process
    # =========================================================================
    pcd_prep = input(
        "Do you want to prepare the point cloud? (y/n): ").lower() == 'y'
    if pcd_prep:
        export_ifc_to_sdf(arc_model, logger)

        proc = launch_ros2_pipeline(logger)

        input("Drive the robot to collect the point cloud, then press Enter to continue...")
        stop_ros2_pipeline(proc, logger)

    else:
        pcd_path = Path("pcd_models/cloudGlobal.pcd")

    # Point cloud cleaning
    cleaned_pcd_path = clean_point_cloud(pcd_path, logger)

    # Point cloud segmentation
    segmented_csv_path = segment_point_cloud(
        cleaned_pcd_path, arc_model, logger)

    # Undefined points exclusion
    excluded_pcd_path, excluded_csv_path = exclude_planes(
        cleaned_pcd_path, segmented_csv_path, logger)

    PCD_MODEL = excluded_pcd_path
    CSV_FILE = excluded_csv_path

    # Point cloud registration
    register_point_clouds(PCD_MODEL, CSV_FILE, arc_model, logger)

    # =========================================================================
    # Merge point cloud with BIM-derived graph
    # =========================================================================
    # Check if the point cloud with the semantic CSV file can be used for querying the BIM graph
    picked_global_id = retrieve_picked_point_id(PCD_MODEL, CSV_FILE, logger)

    with driver.session() as session:
        wall_row = session.execute_read(
            neo4j_ops.retrieve_wall_attr, picked_global_id)

        if wall_row is None:
            print("No wall found")
            return

        print(wall_row["id"])
        print(wall_row["ifcClass"])
        print(wall_row["layerCount"])

    if logger:
        logger.logText("SCAN2GRAPH", "SCAN2GRAPH completed")
