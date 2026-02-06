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

divider = "-" * 100


def graph_initiate():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.logText("PROJECT", "Neo4j driver initiated")
    logger.logText("Divider", divider)
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
    finally:
        # Ensure driver is always closed
        driver.close()
        logger.logText("Divider", divider)
        logger.logText("PROJECT", "Neo4j driver closed")

    logger.logText("PROJECT", "Ended")


# TODO - Till next meeting:
# 1. Pipes need to be connected to layer nodes (light fixtures to walls)
# 2. Extract MEP systems' geometry (But how..?)
# 3. Structural layers should be considered as load bearing elements
# 4. Visual improvement - 3D coordinates (what would be its pros and cons?)

# TODO - Daily:
# - Let's go with the structural layer encoding with Example_STR.ifc
