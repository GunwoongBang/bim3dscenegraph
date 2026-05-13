import numpy as np
import ifcopenshell.util.placement


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",           # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Switches, receptacles, panelboards
]


def _normalize(vec: list[float]) -> np.ndarray | None:
    """
    Normalize a 3D vector. Returns None if the vector has zero length.

    Args:
        vec: Iterable of 3 numbers representing a vector

    Returns:
        ndarray: Normalized vector as a numpy array, or None if input is zero-length
    """
    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return None
    return arr / norm


def _generate_orientation_matrix(mapped_item) -> np.ndarray:
    """
    Generate a 3x3 orientation matrix from an IfcMappedItem's MappingTarget axes.

    Args:
        mapped_item: An IfcMappedItem with a MappingTarget that may have Axis1, Axis2, Axis3

    Returns:
        ndarray: A 3x3 numpy array representing the orientation matrix, or identity if not defined
    """
    mapping_target = getattr(mapped_item, "MappingTarget", None)
    if mapping_target is None:
        return np.eye(3)

    axis1 = getattr(mapping_target, "Axis1", None)
    axis2 = getattr(mapping_target, "Axis2", None)
    axis3 = getattr(mapping_target, "Axis3", None)

    x = np.array(getattr(axis1, "DirectionRatios",
                 (1.0, 0.0, 0.0)), dtype=float)
    y = np.array(getattr(axis2, "DirectionRatios",
                 (0.0, 1.0, 0.0)), dtype=float)
    z = np.array(getattr(axis3, "DirectionRatios",
                 (0.0, 0.0, 1.0)), dtype=float)

    x = _normalize(x)
    y = _normalize(y)
    z = _normalize(z)
    if x is None or y is None or z is None:
        return np.eye(3)

    return np.column_stack((x, y, z))


def _classify_mep_element(element) -> tuple:
    """
    Classify an MEP element's shape type and extract relevant geometric information.

    Args:
        element: IFC element to classify

    Returns:
        Tuple:
        (item, mapped_rot) where:
            - item: The IfcExtrudedAreaSolid representing the main geometry, or None if not found
            - mapped_rot: The orientation matrix from the IfcMappedItem, or identity
    """
    representation = getattr(element, "Representation", None)
    reps = getattr(representation, "Representations", None)
    if not reps:
        return None, np.eye(3)

    for rep in reps:
        items = getattr(rep, "Items", None) or []

        for item in items:
            if item.is_a("IfcExtrudedAreaSolid"):
                return item, np.eye(3)
            if item.is_a("IfcMappedItem"):
                mapping_source = getattr(item, "MappingSource", None)
                mapped_rep = getattr(
                    mapping_source, "MappedRepresentation", None) if mapping_source else None
                mapped_items = getattr(mapped_rep, "Items", None) or []
                for mapped_item in mapped_items:
                    if mapped_item.is_a("IfcExtrudedAreaSolid"):
                        return mapped_item, _generate_orientation_matrix(item)

    return None, np.eye(3)


def extract_shape_signature(element) -> dict:
    """
    Extract shape signature (cylindrical vs rectangular) and dimensions from MEP element IFC geometry.

    Args:
        element: IFC element to analyze

    Returns:
        dict: Dictionary with shapeType ("cylindrical", "rectangular", or "other") and dimensions in mm
    """
    item, _ = _classify_mep_element(element)

    # elements out of scope (e.g. tee, elbow, etc.)
    if item is None:
        return {"shapeType": "other", "radiusMm": None, "xDimMm": None, "yDimMm": None}

    if item.is_a("IfcExtrudedAreaSolid"):
        swept = getattr(item, "SweptArea", None)

        # cylindrical elements (pipes)
        if swept and swept.is_a("IfcCircleProfileDef"):
            radius = getattr(swept, "Radius", None)
            return {"shapeType": "cylindrical", "radiusMm": radius, "xDimMm": None, "yDimMm": None}

        # rectangular elements (switches, receptacles, panelboards)
        if swept and swept.is_a("IfcRectangleProfileDef"):
            x_dim = getattr(swept, "XDim", None)
            y_dim = getattr(swept, "YDim", None)
            return {"shapeType": "rectangular", "radiusMm": None, "xDimMm": x_dim, "yDimMm": y_dim}

    return {"shapeType": "other", "radiusMm": None, "xDimMm": None, "yDimMm": None}


def extract_facing(element) -> list[float] | None:
    """
    Extract the facing direction (local Z-axis) of an IFC element in world coordinates.

    For wall-mounted devices (switches, receptacles, etc.) modeled with a flat
    backplate, the local Z-axis is the outward face normal.

    Args:
        element: IFC element with ObjectPlacement

    Returns:
        List [dx, dy, dz] unit direction vector, or None if extraction fails
    """
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
        return np.round(matrix[:3, 2], 5).tolist()
    except Exception:
        return None
