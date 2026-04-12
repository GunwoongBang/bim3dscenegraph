import os

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


if __name__ == "__main__":
    logger.logText("PROJECT", "Started")
    logger.logText("Divider")

    # =========================================================================
    # BIM2GRAPH: Extract graph from BIM and persist to Neo4j
    # =========================================================================
    # Initiate Neo4j driver for BIM2GRAPH operations
    driver = graph_initiate()

    bim2graph(driver, ARC_PATH, STR_PATH, MEP_PATH, logger)

    # Close driver after BIM2GRAPH operations
    graph_close(driver)
    logger.logText("Divider")

    # =========================================================================
    # SENSOR2GRAPH: Extract point cloud from sensor data and merge with BIM graph
    # =========================================================================
    # Re-initiate driver for SENSOR2GRAPH operations
    driver = graph_initiate()

    pcd_prep = False  # Set to True if point cloud preparation is needed
    sensor2graph(driver, PCD_PATH, ARC_PATH, pcd_prep, logger)

    # Close driver after SENSOR2GRAPH operations
    graph_close(driver)

    logger.logText("Divider")
    logger.logText("PROJECT", "Ended")
