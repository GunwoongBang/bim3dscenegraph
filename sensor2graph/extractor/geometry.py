"""
Geometry utilities for IFC element processing.

Provides shared functions for extracting geometric data from IFC elements,
with consistent unit handling (all outputs in millimeters).
"""

import ifcopenshell
import ifcopenshell.geom
import ifcopenshell.util.placement
import numpy as np


def get_geom_settings():
    """
    Get shared geometry settings for ifcopenshell.

    Returns:
        ifcopenshell.geom.settings configured for world coordinates
    """
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    return settings


def extract_vertices(element):
    settings = get_geom_settings()
    shape = ifcopenshell.geom.create_shape(settings, element)
    return np.array(shape.geometry.verts).reshape(-1, 3)
