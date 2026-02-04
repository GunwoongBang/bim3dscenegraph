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


def m_to_mm(coords):
    """
    Convert coordinates from meters to millimeters.

    Args:
        coords: Array-like coordinates in meters

    Returns:
        List of coordinates in millimeters, rounded to 5 decimal places
    """
    return (np.array(coords) * 1000).round(5).tolist()


def extract_vertices(element):
    """
    Extract world-coordinate vertices from any IFC element.

    Args:
        element: IFC element with geometry

    Returns:
        numpy array of shape (n, 3) containing vertex coordinates in meters

    Raises:
        Exception if geometry extraction fails
    """
    settings = get_geom_settings()
    shape = ifcopenshell.geom.create_shape(settings, element)
    return np.array(shape.geometry.verts).reshape(-1, 3)


def extract_centroid(element):
    """
    Calculate the centroid of an element's geometry in world coordinates.

    Args:
        element: IFC element with geometry

    Returns:
        List [x, y, z] centroid in millimeters, or None if extraction fails
    """
    try:
        verts = extract_vertices(element)
        centroid_m = verts.mean(axis=0)
        return m_to_mm(centroid_m)
    except Exception:
        return None


def extract_bbox(element):
    """
    Extract axis-aligned bounding box (AABB) of an IFC element.

    Args:
        element: IFC element with geometry

    Returns:
        Tuple (bbox_min, bbox_max) in millimeters, or None if extraction fails
        Each is a list [x, y, z]
    """
    try:
        verts = extract_vertices(element)
        bbox_min = m_to_mm(verts.min(axis=0))
        bbox_max = m_to_mm(verts.max(axis=0))
        return bbox_min, bbox_max
    except Exception:
        return None


def extract_placement(element):
    """
    Extract placement matrix components (origin and axis2) from an IFC element.

    The origin is the element's reference point in world coordinates.
    Axis2 is the Y-axis direction of the element's local coordinate system,
    which for walls indicates the layer stratification direction.

    Args:
        element: IFC element with ObjectPlacement

    Returns:
        Tuple (origin, axis2) where:
            - origin: List [x, y, z] in millimeters
            - axis2: List [dx, dy, dz] unit direction vector
        Returns (None, None) if extraction fails
    """
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
        # Origin is the translation component (already in model units, typically mm)
        origin = np.round(matrix[:3, 3], 5).tolist()
        # Axis2 is the Y-axis column (unitless direction vector)
        axis2 = np.round(matrix[:3, 1], 5).tolist()
        return origin, axis2
    except Exception:
        return None, None
