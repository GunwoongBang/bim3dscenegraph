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
from .mep import extract_mep_elements, extract_mep_systems
from .relationships import compute_mep_element_wall_rels, compute_mep_memberships, compute_mep_system_space_rels, compute_space_wall_rels, compute_wall_opening_rels

__all__ = [
    'geometry',
    'get_pset_property',
    'get_material_association',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_str_elements',
    'extract_openings',
    'extract_mep_elements',
    'extract_mep_systems',
    'compute_mep_element_wall_rels',
    'compute_mep_memberships',
    'compute_mep_system_space_rels',
    'compute_space_wall_rels',
    'compute_wall_opening_rels',
]
