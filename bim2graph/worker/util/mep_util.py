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


def _axis2placement_matrix(placement) -> np.ndarray:
    """Build a 4x4 transform from an IfcAxis2Placement3D."""
    loc = np.array(placement.Location.Coordinates, dtype=float)
    z = np.array(
        placement.Axis.DirectionRatios if placement.Axis else (0.0, 0.0, 1.0),
        dtype=float,
    )
    x_ref = np.array(
        placement.RefDirection.DirectionRatios if placement.RefDirection else (1.0, 0.0, 0.0),
        dtype=float,
    )
    z /= np.linalg.norm(z)
    x = x_ref - np.dot(x_ref, z) * z
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    m = np.eye(4)
    m[:3, 0] = x
    m[:3, 1] = y
    m[:3, 2] = z
    m[:3, 3] = loc
    return m


def _extrusion_facing(element, obj_rotation: np.ndarray) -> list[float] | None:
    """
    Derive a world-space facing direction from the element's body representation.

    Handles elements whose ObjectPlacement is identity and whose orientation is
    encoded entirely in an IfcExtrudedAreaSolid inside the Body representation
    (typical for straight pipes/ducts/cable trays in Revit-exported IFCs).
    """
    rep = getattr(element, "Representation", None)
    if rep is None:
        return None
    for shape_rep in rep.Representations:
        if shape_rep.RepresentationIdentifier != "Body":
            continue
        items = shape_rep.Items
        if len(items) != 1 or not items[0].is_a("IfcExtrudedAreaSolid"):
            continue
        solid = items[0]
        solid_rotation = _axis2placement_matrix(solid.Position)[:3, :3]
        ext_dir = np.array(
            solid.ExtrudedDirection.DirectionRatios, dtype=float
        )
        world_dir = obj_rotation @ solid_rotation @ ext_dir
        norm = np.linalg.norm(world_dir)
        if norm == 0:
            return None
        return np.round(world_dir / norm, 5).tolist()
    return None


def extract_facing(element) -> list[float] | None:
    """
    Extract the facing direction of an IFC element as a world-space unit vector.

    Resolution order:
      1. If ObjectPlacement carries a non-identity rotation (wall-mounted devices
         like switches/receptacles), use its local Z-axis as the outward normal.
      2. Otherwise, if the Body representation is a single IfcExtrudedAreaSolid
         (linear MEP elements such as pipes/ducts), use the world-space extrusion
         direction as the run axis.
      3. Otherwise, fall back to the ObjectPlacement local Z (which will be
         (0, 0, 1) when the placement is identity).

    Args:
        element: IFC element with ObjectPlacement

    Returns:
        List [dx, dy, dz] unit direction vector, or None if extraction fails
    """
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
    except Exception:
        return None

    rotation = matrix[:3, :3]
    if not np.allclose(rotation, np.eye(3), atol=1e-6):
        return np.round(rotation[:, 2], 5).tolist()

    try:
        ext = _extrusion_facing(element, rotation)
    except Exception:
        ext = None
    if ext is not None:
        return ext

    return np.round(rotation[:, 2], 5).tolist()
