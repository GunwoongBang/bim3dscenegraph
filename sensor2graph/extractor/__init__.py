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
from .pointcloud import generate_point_cloud, transform_point_cloud, export_point_cloud, visualize_point_cloud

__all__ = [
    'geometry',
    'generate_point_cloud',
    'transform_point_cloud',
    'export_point_cloud',
    'visualize_point_cloud',
]
