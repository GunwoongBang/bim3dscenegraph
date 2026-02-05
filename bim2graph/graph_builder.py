"""
Main orchestrator for BIM-to-Graph conversion.

This module coordinates the extraction of data from IFC models
and persistence to Neo4j graph database.
"""

import ifcopenshell

from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .extractor import (
    extract_spaces,
    extract_walls,
    extract_layers,
    extract_space_wall_edges,
    extract_mep_elements,
    compute_mep_wall_relationships,
)


def generate_graph(driver, ifc_path, logger=None, query_manager=None, mep_path=None):
    """
    Generate a BIM-derived graph from an IFC model and persist to Neo4j.

    This function orchestrates the full ETL pipeline:
        1. Load IFC model
        2. Extract spatial elements (spaces, walls)
        3. Extract material layers
        4. Extract topological relationships
        5. Optionally load MEP model and extract MEP elements
        6. Persist all data to Neo4j

    Args:
        driver: Neo4j driver instance
        ifc_path: Path to the IFC model file
        logger: Optional logger for output messages
        query_manager: Optional QueryManager instance (creates default if None)
        mep_path: Optional path to MEP IFC model file

    Example:
        driver = GraphDatabase.driver(uri, auth=(user, password))
        generate_graph(driver, "model.ifc", logger=my_logger, mep_path="mep.ifc")
    """
    if logger:
        logger.logText("BIM2GRAPH", f"Loading IFC model from {ifc_path}")

    # Initialize components
    if query_manager is None:
        query_manager = QueryManager()

    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC model
    model = ifcopenshell.open(ifc_path)

    # =========================================================================
    # Extract data from IFC
    # =========================================================================
    spaces = extract_spaces(model, logger)
    walls = extract_walls(model, logger)
    layers = extract_layers(model, walls, logger)
    space_wall_edges = extract_space_wall_edges(model, spaces, walls, logger)

    # Extract MEP elements if MEP model is provided
    mep_elements = []
    mep_wall_edges = []
    if mep_path:
        if logger:
            logger.logText("BIM2GRAPH", f"Loading MEP model from {mep_path}")
        mep_model = ifcopenshell.open(mep_path)
        mep_elements = extract_mep_elements(mep_model, logger)
        mep_wall_edges = compute_mep_wall_relationships(
            mep_elements, walls, logger=logger)

    # =========================================================================
    # Persist to Neo4j
    # =========================================================================
    with driver.session() as session:
        # Reset and setup schema
        session.execute_write(neo4j_ops.reset_database)
        session.execute_write(neo4j_ops.ensure_schema)

        # Create nodes
        if spaces:
            session.execute_write(neo4j_ops.upsert_spaces, spaces)
        if walls:
            session.execute_write(neo4j_ops.upsert_walls, walls)
        if layers:
            session.execute_write(neo4j_ops.upsert_layers, layers)
            session.execute_write(neo4j_ops.create_wall_layer_edges, layers)

        # Create relationships
        if space_wall_edges:
            session.execute_write(
                neo4j_ops.create_space_wall_edges, space_wall_edges)

        # Create MEP nodes and relationships
        if mep_elements:
            session.execute_write(neo4j_ops.upsert_mep_elements, mep_elements)
        if mep_wall_edges:
            session.execute_write(
                neo4j_ops.create_mep_wall_edges, mep_wall_edges)

    if logger:
        logger.logText("BIM2GRAPH", "Graph generation completed")
