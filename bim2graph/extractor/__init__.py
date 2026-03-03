"""
IFC data extraction modules.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - utils.wall_utils: Wall IFC utilities (property/material extraction)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - openings: Opening extraction and wall-opening relations
    - relationships: Topological relationships (space-wall boundaries)
    - mep: MEP node extraction and relationships
"""

from . import geometry
from .utils.wall_utils import get_pset_property, get_material_association
from .spaces import extract_spaces
from .walls import extract_walls, extract_layers, extract_str_elements
from .openings import extract_openings
from .relationships import compute_mep_memberships, ccompute_space_wall_edges, compute_wall_opening_edges
from .mep import (
    extract_mep_elements,
    extract_mep_systems,
    compute_mep_wall_relationships,
    compute_mep_system_space_edges,
)

__all__ = [
    'geometry',
    'get_pset_property',
    'get_material_association',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_str_elements',
    'extract_openings',
    'compute_wall_opening_edges',
    'ccompute_space_wall_edges',
    'extract_mep_elements',
    'extract_mep_systems',
    'compute_mep_memberships',
    'compute_mep_wall_relationships',
    'compute_mep_system_space_edges',
    'enrich_mep_geometry_for_wall_penetrations',
]
