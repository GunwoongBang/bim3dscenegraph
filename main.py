import os
from neo4j import GraphDatabase
from dotenv import load_dotenv
from bim2graph import generate_graph
import logger as logger

load_dotenv()

ARC_PATH = "ifc_models/Example/Example_ARC.ifc"
STR_PATH = "ifc_models/Example/Example_STR.ifc"
MEP_PATH = "ifc_models/Example/Example_MEP.ifc"

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    raise RuntimeError("Neo4j credentials not found")


def graph_initiate():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.logText("PROJECT", "Neo4j driver initiated")
    logger.logText("Divider")
    return driver


if __name__ == "__main__":
    logger.logText("PROJECT", "Started")

    # Create driver once for all operations
    driver = graph_initiate()

    try:
        # ====================================================================
        # BIM2GRAPH
        # ====================================================================

        # Generate a BIM-derived graph from BIM models (ARC + MEP)
        generate_graph(driver, arc_path=ARC_PATH,
                       str_path=STR_PATH, mep_path=MEP_PATH, logger=logger)

        # ====================================================================
        # SENSOR2GRAPH
        # ====================================================================

        # ====================================================================
        # GRAPH MERGING
        # ====================================================================
    except Exception as e:
        logger.logText("PROJECT", f"Error: {e}")
    finally:
        # Ensure driver is always closed
        driver.close()
        logger.logText("Divider")
        logger.logText("PROJECT", "Neo4j driver closed")

    logger.logText("PROJECT", "Ended")


"""
TODO - Future works:
    1. Extract MEP systems' geometry - bounding box or center point
    2. Visual improvement - 3D coordinates (what would be its pros and cons?)

NOTE - What's been done:
    1. Sturctural elements are extracted from the STR model and matched with ARC layers
    2. MEP elements are extracted from the MEP model and connected to wall layers
        + MEP-Wall relationships are computed based on bounding box intersection
        + MEP cannot be connected to layers due to lack of geometric information - 
"""
