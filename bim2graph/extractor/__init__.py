"""
IFC data extraction modules.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - relationships: Topological relationships (space-wall boundaries)
    - mep: MEP element extraction and wall relationships
"""

from . import geometry
from .spaces import extract_spaces
from .walls import extract_walls, extract_layers
from .relationships import extract_space_wall_edges
from .mep import extract_mep_elements, compute_mep_wall_relationships

__all__ = [
    'geometry',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_space_wall_edges',
    'extract_mep_elements',
    'compute_mep_wall_relationships',
    'extract_space_wall_edges',
]
