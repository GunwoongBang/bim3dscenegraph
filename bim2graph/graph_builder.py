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
    extract_str_elements,
    extract_openings_and_edges,
    extract_space_wall_edges,
    extract_mep_elements,
    extract_mep_systems,
    extract_mep_system_memberships,
    compute_mep_wall_relationships,
    compute_mep_system_parent_edges,
    enrich_mep_geometry_for_wall_penetrations,
)


def bim2graph(driver, arc_path, str_path=None, mep_path=None, logger=None):
    """
    Generate a BIM-derived graph from an IFC model and persist to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract spatial elements (spaces, walls)
        3. Extract material layers
        4. Encode structural elements based on STR model
        5. Load MEP model and extract MEP elements
        6. Persist all data to Neo4j

    Args:
        driver: Neo4j driver instance
        arc_path: Path to the architectural IFC model file
        str_path: Path to the structural IFC model file
        mep_path: Path to the MEP IFC model file
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText(
            "BIM2GRAPH", f'ARC{", STR" if str_path else None}{", MEP" if mep_path else None} IFC models loaded')

    # Initialize components
    query_manager = QueryManager()
    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC models
    arc_model = ifcopenshell.open(arc_path)
    str_model = ifcopenshell.open(str_path) if str_path else None
    mep_model = ifcopenshell.open(mep_path) if mep_path else None

    # =========================================================================
    # Extract data from IFC
    # =========================================================================
    spaces = extract_spaces(arc_model, logger)
    walls = extract_walls(arc_model, logger)

    # Extract structural elements if STR model is provided
    str_elements = extract_str_elements(
        str_model, logger) if str_model else None
    layers = extract_layers(arc_model, walls, str_elements, logger)
    openings, wall_opening_edges = extract_openings_and_edges(
        arc_model, walls, logger)

    space_wall_edges = extract_space_wall_edges(
        arc_model, spaces, walls, logger)

    # Extract MEP elements if MEP model is provided
    mep_elements = []
    mep_systems = []
    mep_wall_edges = []
    mep_system_memberships = []
    mep_system_space_edges = []
    if mep_model:
        mep_elements = extract_mep_elements(mep_model, logger)
        mep_systems = extract_mep_systems(mep_model, logger)
        mep_system_memberships = extract_mep_system_memberships(
            mep_model, mep_elements, logger)
        mep_wall_edges = compute_mep_wall_relationships(
            mep_model, mep_elements, walls, logger=logger)
        if mep_wall_edges:
            mep_elements = enrich_mep_geometry_for_wall_penetrations(
                mep_model,
                mep_elements,
                mep_wall_edges,
                walls,
                logger=logger,
            )
        if mep_systems and mep_system_memberships:
            mep_system_space_edges = compute_mep_system_parent_edges(
                arc_model,
                mep_model,
                mep_systems,
                mep_system_memberships,
                mep_elements,
                logger=logger,
            )

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
        if openings:
            session.execute_write(neo4j_ops.upsert_openings, openings)
        if wall_opening_edges:
            session.execute_write(
                neo4j_ops.create_wall_opening_edges,
                wall_opening_edges,
            )

        # Create relationships
        if space_wall_edges:
            session.execute_write(
                neo4j_ops.create_space_wall_edges, space_wall_edges)

        # Create MEP nodes and relationships
        if mep_elements:
            session.execute_write(neo4j_ops.upsert_mep_elements, mep_elements)
        if mep_systems:
            session.execute_write(neo4j_ops.upsert_mep_systems, mep_systems)
        if mep_system_memberships:
            session.execute_write(
                neo4j_ops.create_mep_system_mep_edges, mep_system_memberships)
        if mep_wall_edges:
            session.execute_write(
                neo4j_ops.create_mep_wall_edges, mep_wall_edges)
        if mep_system_space_edges:
            session.execute_write(
                neo4j_ops.create_mep_system_space_edges,
                mep_system_space_edges,
            )

    if logger:
        logger.logText("BIM2GRAPH", "Graph generation completed")
