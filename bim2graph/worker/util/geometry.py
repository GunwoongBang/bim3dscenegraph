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


def _m_to_mm(coords: list[float]) -> list[float]:
    """
    Convert a scalar or array-like length from meters to millimeters.

    Args:
        coords: Scalar or array-like coordinates in meters, or None

    Returns:
        Same shape as input (scalar or list) in millimeters rounded to 2
        decimals, or None if input is None
    """
    if coords is None:
        return None
    return (np.array(coords) * 1000).round(2).tolist()


def _extract_vertices(element) -> np.ndarray:
    """
    Extract world-coordinate vertices from any IFC element.

    Args:
        element: IFC element with geometry

    Returns:
        Array: numpy array of shape (n, 3) containing vertex coordinates in meters
    """
    settings = _get_geom_settings()
    shape = ifcopenshell.geom.create_shape(settings, element)
    return np.array(shape.geometry.verts).reshape(-1, 3)


def extract_bbox(element) -> tuple[list[float], list[float]]:
    """
    Extract axis-aligned bounding box (AABB) of an IFC element.

    Args:
        element: IFC element with geometry

    Returns:
        Tuple:
            - Tuple (bbox_min, bbox_max) in millimeters, or None if extraction fails
            - Each is a list [x, y, z]
    """
    try:
        verts = _extract_vertices(element)
        bbox_min = _m_to_mm(verts.min(axis=0))
        bbox_max = _m_to_mm(verts.max(axis=0))
        return bbox_min, bbox_max
    except Exception:
        return None, None


def extract_centroid(element) -> list[float] | None:
    """
    Calculate the centroid of an element's geometry in world coordinates.

    Args:
        element: IFC element with geometry

    Returns:
        List: List [x, y, z] centroid in millimeters, or None if extraction fails
    """
    try:
        verts = _extract_vertices(element)
        centroid_m = verts.mean(axis=0)
        return _m_to_mm(centroid_m)
    except Exception:
        return None
