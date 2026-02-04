"""
IFC data extraction modules.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - relationships: Topological relationships (space-wall boundaries)
"""

from . import geometry
from .spaces import extract_spaces
from .walls import extract_walls, extract_layers
from .relationships import extract_space_wall_edges

__all__ = [
    'geometry',
    'extract_spaces',
    'extract_walls',
    'extract_layers',
    'extract_space_wall_edges',
]
