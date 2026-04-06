import os
import traceback

from pathlib import Path
from dotenv import load_dotenv
from neo4j import GraphDatabase

from bim2graph import bim2graph
from sensor2graph import sensor2graph

import logger

load_dotenv()

ARC_PATH = Path("ifc_models/Example/Example_ARC.ifc")
STR_PATH = Path("ifc_models/Example/Example_STR.ifc")
MEP_PATH = Path("ifc_models/Example/Example_MEP.ifc")
PCD_PATH = Path("pc_models/cloudGlobal.pcd")

NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USER = os.getenv("NEO4J_USER")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
    raise RuntimeError("Neo4j credentials not found")


def graph_initiate():
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    logger.logText("PROJECT", "Neo4j driver initiated")
    return driver


def graph_close(driver):
    driver.close()
    logger.logText("PROJECT", "Neo4j driver closed")
    print("Neo4j host: http://localhost:7474/browser/")


if __name__ == "__main__":
    logger.logText("PROJECT", "Started")
    logger.logText("Divider")

    # Create driver once for all operations
    driver = graph_initiate()

    # =========================================================================
    # BIM2GRAPH: Extract graph from BIM and persist to Neo4j
    # =========================================================================
    bim2graph(driver, ARC_PATH, STR_PATH, MEP_PATH, logger)

    # Close driver after BIM2GRAPH operations
    graph_close(driver)
    logger.logText("Divider")

    # =========================================================================
    # SENSOR2GRAPH: Extract graph from sensor data and merge with BIM graph
    # =========================================================================
    sensor2graph(PCD_PATH, ARC_PATH, logger)

    logger.logText("Divider")
    logger.logText("PROJECT", "Ended")
