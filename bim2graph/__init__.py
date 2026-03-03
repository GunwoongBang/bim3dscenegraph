"""
BIM2GRAPH - Convert IFC models to Neo4j property graphs.

This package provides tools for extracting building information from IFC files
and persisting it as a graph database in Neo4j.

Main entry point:
    from bim2graph import generate_graph
    
    driver = GraphDatabase.driver(uri, auth=(user, password))
    bim2graph(driver, "path/to/model.ifc")

Package structure:
    - extractor/: IFC data extraction modules
        - geometry.py: Geometry utilities (centroid, bbox, placement)
        - spaces.py: Space element extraction
        - walls.py: Wall and material layer extraction
        - relationships.py: Topological relationships
    - persistence/: Neo4j database operations
        - neo4j_ops.py: CRUD operations
    - query_manager.py: Cypher query file loader
    - graph_builder.py: Main orchestrator
"""

from .extractor.relationships import compute_mep_memberships

from .graph_builder import bim2graph
from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .extractor import (
    extract_spaces,
    extract_walls,
    extract_layers,
    extract_str_elements,
    ccompute_space_wall_edges,
    extract_mep_elements,
    extract_mep_systems,
    compute_mep_wall_relationships,
    compute_mep_system_space_edges,
    get_pset_property,
    geometry,
)

__version__ = "0.1.0"

__all__ = [
    # Main entry point
    'bim2graph',

    # Core classes
    'QueryManager',
    'Neo4jOperations',

    # Extraction functions
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_str_elements',
    'ccompute_space_wall_edges',
    'extract_mep_elements',
    'extract_mep_systems',
    'compute_mep_memberships',
    'compute_mep_wall_relationships',
    'compute_mep_system_space_edges',
    'get_pset_property',
    'geometry',
]
