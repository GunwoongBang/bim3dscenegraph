"""
Main orchestrator for BIM-to-Graph conversion.

This module coordinates the extraction of data from IFC models
and persistence to Neo4j graph database.
"""

import ifcopenshell

from .extractor.relationships import compute_mep_element_wall_rels, compute_mep_memberships, compute_mep_system_space_rels

from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .extractor import (
    extract_spaces,
    extract_walls,
    extract_layers,
    extract_str_elements,
    extract_openings,
    compute_wall_opening_rels,
    compute_space_wall_rels,
    extract_mep_elements,
    extract_mep_systems,
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
    # Extract nodes
    spaces = extract_spaces(arc_model, logger)
    walls = extract_walls(arc_model, logger)

    if str_model:
        str_elements = extract_str_elements(str_model, logger)

    layers = extract_layers(arc_model, walls, str_elements, logger)
    openings = extract_openings(arc_model, logger)

    if mep_model:
        mep_systems = extract_mep_systems(mep_model, logger)
        mep_elements = extract_mep_elements(arc_model, mep_model, logger)

    # Extract relationships
    space_wall_rels = compute_space_wall_rels(
        arc_model, spaces, walls, logger)
    wall_opening_rels = compute_wall_opening_rels(arc_model, logger)

    if mep_model:
        mep_memberships = compute_mep_memberships(
            mep_model, mep_elements, logger)
        mep_element_wall_rels = compute_mep_element_wall_rels(
            mep_elements, walls, logger)

        if mep_systems and mep_memberships:
            mep_system_space_rels = compute_mep_system_space_rels(
                arc_model,
                mep_model,
                mep_systems,
                mep_memberships,
                mep_elements,
                logger,
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
        if openings:
            session.execute_write(neo4j_ops.upsert_openings, openings)
        if mep_systems:
            session.execute_write(neo4j_ops.upsert_mep_systems, mep_systems)
        if mep_elements:
            session.execute_write(neo4j_ops.upsert_mep_elements, mep_elements)

        # Create relationships
        if space_wall_rels:
            session.execute_write(
                neo4j_ops.create_space_wall_rels, space_wall_rels)
        if layers:
            session.execute_write(neo4j_ops.create_wall_layer_rels, layers)
        if wall_opening_rels:
            session.execute_write(
                neo4j_ops.create_wall_opening_rels, wall_opening_rels)
        if mep_memberships:
            session.execute_write(
                neo4j_ops.create_mep_system_mep_element_rels, mep_memberships)
        if mep_system_space_rels:
            session.execute_write(
                neo4j_ops.create_mep_system_space_rels, mep_system_space_rels)
        if mep_element_wall_rels:
            session.execute_write(
                neo4j_ops.create_mep_element_wall_rels, mep_element_wall_rels)

    if logger:
        logger.logText("BIM2GRAPH", "Graph generation completed\n")
