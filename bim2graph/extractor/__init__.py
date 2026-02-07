"""
IFC data extraction modules.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - ifc_utils: Shared IFC utilities (property/material extraction)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - relationships: Topological relationships (space-wall boundaries)
    - mep: MEP element extraction and wall relationships
"""

from . import geometry
from .ifc_utils import get_pset_property, get_material_association
from .spaces import extract_spaces
from .walls import extract_walls, extract_layers, extract_str_elements
from .relationships import extract_space_wall_edges
from .mep import extract_mep_elements, compute_mep_wall_relationships

__all__ = [
    'geometry',
    'get_pset_property',
    'get_material_association',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_str_elements',
    'extract_space_wall_edges',
    'extract_mep_elements',
    'compute_mep_wall_relationships',
]
