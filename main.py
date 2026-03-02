import os
import traceback
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bim2graph import bim2graph
from sensor2graph import sensor2graph
import logger as logger

load_dotenv()

ARC_PATH = "ifc_models/Example/Example_ARC.ifc"
STR_PATH = "ifc_models/Example/Example_STR.ifc"
MEP_PATH = "ifc_models/Example/Example_MEP.ifc"
# Old file - need to be replaced with the current model
PCD_PATH = "ifc_models/Example/Example_PCD.ifc"

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    raise RuntimeError("Neo4j credentials not found")


def graph_initiate():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.logText("PROJECT", "Neo4j driver initiated")
    print("Neo4j host: http://localhost:7474/browser/")
    logger.logText("Divider")
    return driver


if __name__ == "__main__":
    logger.logText("PROJECT", "Started")

    # Create driver once for all operations
    driver = graph_initiate()

    try:
        # Generate a BIM-derived graph from BIM models (ARC + STR + MEP)
        bim2graph(driver, arc_path=ARC_PATH,
                  str_path=STR_PATH, mep_path=MEP_PATH, logger=logger)

        # Generate a Sensor-derived graph from BIM models (PCD)
        sensor2graph(driver, pcd_path=PCD_PATH, logger=logger)

        # ====================================================================
        # GRAPH MERGING
        # ====================================================================

    except Exception as e:
        logger.logText("PROJECT", f"Error: {e}")
        logger.logText("PROJECT", f"Traceback:\n{traceback.format_exc()}")
    finally:
        # Ensure driver is always closed
        driver.close()
        logger.logText("Divider")
        logger.logText("PROJECT", "Neo4j driver closed")

    logger.logText("PROJECT", "Ended")


"""
TODO - Future works:
    0. Documentations

    + Here, graph merging means to integrate the BIM-derived graph and the Sensor-derived 3D map into a unified graph representation
    based on 3D scene graph concept, where nodes represent entities
    + BIM-derived graph should utilize IFC components and their properties as much as possible

NOTE - Code review:
    + The current code structure is not so consistent
    + Wall has bbox but they are not really necessary, but it is used for extracting MEMElement wall relationships
        + MEPElement-wall relationships should be created topologically, not based on bounding box intersection
"""
