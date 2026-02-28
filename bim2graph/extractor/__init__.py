"""
IFC data extraction modules.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - ifc_utils: Shared IFC utilities (property/material extraction)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - openings: Opening extraction and wall-opening relations
    - relationships: Topological relationships (space-wall boundaries)
    - mep: MEP node extraction and relationships
"""

from . import geometry
from .ifc_utils import get_pset_property, get_material_association
from .spaces import extract_spaces
from .walls import extract_walls, extract_layers, extract_str_elements
from .openings import extract_openings_and_edges
from .relationships import extract_space_wall_edges
from .mep import (
    extract_mep_elements,
    extract_mep_systems,
    extract_mep_system_memberships,
    compute_mep_wall_relationships,
    compute_mep_system_parent_edges,
    enrich_mep_geometry_for_wall_penetrations,
)

__all__ = [
    'geometry',
    'get_pset_property',
    'get_material_association',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_str_elements',
    'extract_openings_and_edges',
    'extract_space_wall_edges',
    'extract_mep_elements',
    'extract_mep_systems',
    'extract_mep_system_memberships',
    'compute_mep_wall_relationships',
    'compute_mep_system_parent_edges',
    'enrich_mep_geometry_for_wall_penetrations',
]
