"""
Geometry utilities for IFC element processing.

Provides shared functions for extracting geometric data from IFC elements,
with consistent unit handling (all outputs in millimeters).
"""

import ifcopenshell
import ifcopenshell.geom
import numpy as np


def _get_geom_settings():
    """
    Get shared geometry settings for ifcopenshell.

    Returns:
        ifcopenshell.geom.settings configured for world coordinates
    """
    settings = ifcopenshell.geom.settings()
    settings.set(settings.USE_WORLD_COORDS, True)
    return settings


def extract_mesh_from_shape(element):
    """
    Extract vertices and faces from an ifcopenshell shape.

    Args:
        element: IFC element with geometry

    Returns:
        vertices: numpy array of shape (N, 3) - 3D vertex coordinates
        faces: numpy array of shape (M, 3) - triangle face indices
        materials: list of geometry materials (may be empty)
    """
    settings = _get_geom_settings()
    shape = ifcopenshell.geom.create_shape(settings, element)

    # Convert flat vertex list to (N, 3) array
    vertices = np.array(shape.geometry.verts).reshape(-1, 3)

    # Convert flat face list to (M, 3) array (triangles)
    faces = np.array(shape.geometry.faces).reshape(-1, 3)

    return vertices, faces, shape.geometry.materials
