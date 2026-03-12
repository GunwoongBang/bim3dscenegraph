"""
Main extractor module for BIM2GRAPH.

This package provides functions for extracting data from IFC models:
    - geometry: Low-level geometry utilities (centroid, bbox, placement)
    - utils.wall_utils: Wall IFC utilities (property/material extraction)
    - spaces: Space element extraction
    - walls: Wall and material layer extraction
    - openings: Opening extraction and wall-opening relations
    - mep: MEP node extraction and relationships
    - relationships: Topological relationships (space-wall boundaries)
"""

from .space import extract_spaces
from .wall import extract_walls, extract_layers, extract_str_elements
from .opening import extract_openings
from .mep import extract_mep_elements, extract_mep_systems
from .relationship import compute_mep_element_wall_rels, compute_mep_memberships, compute_mep_system_space_rels, compute_space_wall_rels, compute_wall_opening_rels

__all__ = [
    "extract_spaces",
    "extract_walls",
    "extract_layers",
    "extract_str_elements",
    "extract_openings",
    "extract_mep_elements",
    "extract_mep_systems",
    "compute_mep_element_wall_rels",
    "compute_mep_memberships",
    "compute_mep_system_space_rels",
    "compute_space_wall_rels",
    "compute_wall_opening_rels",
]
