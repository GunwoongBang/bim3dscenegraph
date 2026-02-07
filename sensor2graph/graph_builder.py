"""
Main orchestrator for Sensor-to-Graph conversion.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import ifcopenshell
import ifcopenshell.geom

from .query_manager import QueryManager
from .persistence import Neo4jOperations
# import ifcopenshell.geom

# ifc = ifcopenshell.open("ifc_models/Example/Example_ARC.ifc")

# settings = ifcopenshell.geom.settings()
# settings.set(settings.USE_WORLD_COORDS, True)

# for product in ifc.by_type("IfcProduct"):
#     if product.is_a("IfcWall"):
#         shape = ifcopenshell.geom.create_shape(settings, product)
#         print(f"Wall: {product.GlobalId}, Geometry: {shape.geometry}")


def sensor2graph(driver, pcd_path, logger=None):
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
        logger.logText("SENSOR2GRAPH", "PCD IFC model loaded")

    # Initialize components
    query_manager = QueryManager()

    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)

    for element in model.by_type("IfcProduct"):
        if element.is_a("IfcWall"):
            shape = ifcopenshell.geom.create_shape(settings, element)
            geometry = shape.geometry
            logger.logText(
                "SENSOR2GRAPH", f"Processing wall: {element.GlobalId}")
            logger.logText("SENSOR2GRAPH", f"Geometry: {geometry}")

    logger.logText("SENSOR2GRAPH", "Geometry extraction under construction")
