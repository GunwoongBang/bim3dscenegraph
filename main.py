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
PCD_PATH = "ifc_models/Example/Example_PCD.ifc"

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
        # Generate a BIM-derived graph from BIM models (ARC + STR + MEP)
        bim2graph(driver, arc_path=ARC_PATH,
                  str_path=STR_PATH, mep_path=MEP_PATH, logger=logger)

        # Generate a Sensor-derived graph from BIM models (ARC for now, later replaced by PCD_PATH)
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
    1. Extract MEP systems' geometry with bounding box -- then do we need just depth values?
    2. Visual improvement - 3D coordinates (what would be its pros and cons?)
    3. What should be the next step? 
        * Scaling up the BIM2GRAPH pipeline with a bigger IFC model? Or move on to SENSOR2GRAPH and then merging
    4. Also think about how to match two different graphs and 3D representations

NOTE - What's been done:
    1. BIM2GRAPH pipeline for ARC and STR models (MEP model is still pending)
    2. SENSOR2GRAPH pipeline set up for ARC model (later replaced by PCD_PATH)
"""
