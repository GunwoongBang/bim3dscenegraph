"""
Main orchestrator for BIM-to-Graph conversion.

This module coordinates the extraction of data from IFC models
and persistence to Neo4j graph database.
"""

import ifcopenshell

from neo4j import Driver
from pathlib import Path

from query_manager import QueryManager
from .persistence import Neo4jOperations
from .worker import (
    extract_buildings,
    extract_storeys,
    compute_building_storey_rels,
    compute_storey_space_rels,
    extract_spaces,
    extract_walls,
    extract_str_elements,
    extract_layers,
    extract_openings,
    extract_mep_systems,
    extract_mep_elements,
    compute_wall_opening_rels,
    compute_space_wall_rels,
    compute_mep_memberships,
    compute_mep_element_wall_rels,
    compute_space_mep_element_rels,
)


def bim2graph(driver: Driver, arc_path: Path, str_path: Path = None, mep_path: Path = None, logger=None):
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
        mep_elements = extract_mep_elements(mep_model, logger)

    # Extract spatial relationships (needed to derive storey/building centers)
    building_storey_rels = compute_building_storey_rels(arc_model, logger)
    storey_space_rels = compute_storey_space_rels(arc_model, logger)

    # Only storeys that contain rooms are retained (and given a center point);
    # buildings derive their center from those retained storeys.
    storeys = extract_storeys(arc_model, spaces, storey_space_rels, logger)
    buildings = extract_buildings(arc_model, storeys, building_storey_rels, logger)

    # Drop Building-Storey edges pointing to storeys that were not retained
    retained_storey_ids = {s["id"] for s in storeys}
    building_storey_rels = [
        rel for rel in building_storey_rels
        if rel["storey_id"] in retained_storey_ids
    ]

    # Extract remaining relationships
    space_wall_rels = compute_space_wall_rels(
        arc_model, spaces, walls, logger)
    wall_opening_rels = compute_wall_opening_rels(arc_model, logger)

    if mep_model:
        mep_memberships = compute_mep_memberships(
            mep_model, mep_elements, logger)
        mep_element_wall_rels = compute_mep_element_wall_rels(
            mep_elements, walls, logger)
        mep_element_space_rels = compute_space_mep_element_rels(
            mep_elements, spaces, logger)

    # =========================================================================
    # Persist to Neo4j
    # =========================================================================
    with driver.session() as session:
        # Reset and setup schema
        session.execute_write(neo4j_ops.reset_database)
        session.execute_write(neo4j_ops.ensure_schema)

        # Create nodes
        if buildings:
            session.execute_write(neo4j_ops.upsert_buildings, buildings)
        if storeys:
            session.execute_write(neo4j_ops.upsert_storeys, storeys)
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
        if building_storey_rels:
            session.execute_write(
                neo4j_ops.create_building_storey_rels, building_storey_rels)
        if storey_space_rels:
            session.execute_write(
                neo4j_ops.create_storey_space_rels, storey_space_rels)
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
        if mep_element_wall_rels:
            session.execute_write(
                neo4j_ops.create_mep_element_wall_rels, mep_element_wall_rels)
        if mep_element_space_rels:
            session.execute_write(
                neo4j_ops.create_mep_element_space_rels, mep_element_space_rels)

    if logger:
        logger.logText("BIM2GRAPH", "BIM2GRAPH completed")
