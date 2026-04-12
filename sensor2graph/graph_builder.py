"""
Main orchestrator for SENSOR2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import ifcopenshell

from neo4j import Driver
from pathlib import Path

from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .worker import (
    clean_point_cloud,
    segment_point_cloud,
    exclude_planes,
    retrieve_picked_point_id,
)


def sensor2graph(driver: Driver, pcd_path: Path, arc_path: Path, pcd_prep: bool = False, logger=None):
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
        pcd_prep: Boolean flag to indicate if point cloud preparation is needed
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText("SENSOR2GRAPH", "ARC IFC model loaded")

    # Load ARC IFC model
    arc_model = ifcopenshell.open(arc_path)

    # load PCD model and CSV results
    PCD_MODEL = Path("pc_models/cloudGlobal_cleaned_excluded.pcd")
    CSV_FILE = Path("pc_models/cloudGlobal_cleaned_excluded.csv")

    # =========================================================================
    # Clean & Segment & filter point cloud
    # =========================================================================
    # Point cloud preparation (point cloud cleaning, plane segmentation, plane exclusion)
    if pcd_prep is True:
        cleaned_pcd_path = clean_point_cloud(pcd_path, logger)

        segmented_csv_path = segment_point_cloud(
            cleaned_pcd_path, arc_model, logger)

        excluded_pcd_path, excluded_csv_path = exclude_planes(
            cleaned_pcd_path, segmented_csv_path, logger)

        PCD_MODEL = excluded_pcd_path
        CSV_FILE = excluded_csv_path

    # =========================================================================
    # Merge point cloud with BIM-derived graph
    # =========================================================================
    picked_global_id = retrieve_picked_point_id(PCD_MODEL, CSV_FILE, logger)

    with driver.session() as session:
        result = session.run(
            "MATCH (w:Wall {id: $element_id}) "
            "RETURN w.id AS id, w.name AS name, w.layerCount AS layerCount",
            element_id=picked_global_id,
        )

        rows = list(result)
        if not rows:
            print("No wall found")
            return

        for row in rows:
            print(row["id"])
            print(row["layerCount"])

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
