import numpy as np
import ifcopenshell.util.placement as placement_util


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",           # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Switches, receptacles, panelboards
]


def _classify_mep_element(element) -> object | None:
    """
    Find the IfcExtrudedAreaSolid representing an MEP element's main geometry.

    When an element is built from several extrusions (e.g. a receptacle body
    plus a thin faceplate), the one with the greatest Depth is treated as the
    representative solid and the shallower ones are discarded.

    Args:
        element: IFC element to classify

    Returns:
        The deepest IfcExtrudedAreaSolid, or None if none is found
    """
    representation = getattr(element, "Representation", None)
    reps = getattr(representation, "Representations", None)
    if not reps:
        return None

    solids = []
    for rep in reps:
        items = getattr(rep, "Items", None) or []

        for item in items:
            if item.is_a("IfcExtrudedAreaSolid"):
                solids.append(item)
            if item.is_a("IfcMappedItem"):
                mapping_source = getattr(item, "MappingSource", None)
                mapped_rep = getattr(
                    mapping_source, "MappedRepresentation", None) if mapping_source else None
                mapped_items = getattr(mapped_rep, "Items", None) or []
                for mapped_item in mapped_items:
                    if mapped_item.is_a("IfcExtrudedAreaSolid"):
                        solids.append(mapped_item)

    if not solids:
        return None

    return max(solids, key=lambda s: s.Depth)


def extract_shape_signature(element) -> str:
    """
    Classify an MEP element's geometric shape from its IFC representation.

    Args:
        element: IFC element to analyze

    Returns:
        str: "cylindrical", "rectangular", or "other"
    """
    item = _classify_mep_element(element)
    if item is None or not item.is_a("IfcExtrudedAreaSolid"):
        return "other"

    swept = getattr(item, "SweptArea", None)
    if swept is None:
        return "other"
    if swept.is_a("IfcCircleProfileDef"):
        return "cylindrical"
    if swept.is_a("IfcRectangleProfileDef"):
        return "rectangular"
    return "other"


def extract_shape_dimensions(element) -> dict:
    """
    Extract native IFC dimensions of an MEP element in millimeters.

    Dimensions are read directly from the element's IfcExtrudedAreaSolid
    (SweptArea profile + Depth) rather than from its AABB.

    Args:
        element: IFC element to analyze

    Returns:
        dict: Keys vary by shape type:
            - cylindrical: {radius, length}
            - rectangular: {sizeX, sizeY, sizeZ}  (XDim, YDim, extrusion Depth)
            - other:       {} (empty)
        All values are in millimeters.
    """
    item = _classify_mep_element(element)
    if item is None or not item.is_a("IfcExtrudedAreaSolid"):
        return {}

    swept = getattr(item, "SweptArea", None)
    depth = getattr(item, "Depth", None)

    if swept and swept.is_a("IfcCircleProfileDef"):
        return {
            "radius": round(getattr(swept, "Radius", None), 2),
            "length": round(depth, 2),
        }

    if swept and swept.is_a("IfcRectangleProfileDef"):
        return {
            "sizeX": round(getattr(swept, "XDim", None), 2),
            "sizeY": round(getattr(swept, "YDim", None), 2),
            "sizeZ": round(depth, 2),
        }

    return {}


def _axis2placement_matrix(placement) -> np.ndarray:
    """Build a 4x4 transform from an IfcAxis2Placement3D."""
    loc = np.array(placement.Location.Coordinates, dtype=float)
    z = np.array(
        placement.Axis.DirectionRatios if placement.Axis else (0.0, 0.0, 1.0),
        dtype=float,
    )
    x_ref = np.array(
        placement.RefDirection.DirectionRatios if placement.RefDirection else (
            1.0, 0.0, 0.0),
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


def _solid_world_matrix(element, solid) -> np.ndarray:
    """
    4x4 transform mapping the solid's local frame to world coordinates (mm).

    Chains the solid's own placement with the element's ObjectPlacement. Any
    IfcMappedItem transform is assumed identity, which holds for the Revit
    exports handled here (MappingOrigin and MappingTarget are both identity).
    """
    m_solid = _axis2placement_matrix(solid.Position)
    obj_placement = getattr(element, "ObjectPlacement", None)
    if obj_placement is not None:
        m_obj = np.array(
            placement_util.get_local_placement(obj_placement), dtype=float)
    else:
        m_obj = np.eye(4)
    return m_obj @ m_solid


def _unit(vec: np.ndarray) -> list[float] | None:
    """Normalize a vector to a rounded unit list, or None if degenerate."""
    norm = np.linalg.norm(vec)
    if norm == 0:
        return None
    return np.round(vec / norm, 5).tolist()


def extract_extruded_direction(element) -> list[float] | None:
    """
    Compute the world-space extrusion direction of an MEP element.

    The element's IfcExtrudedAreaSolid defines its extrusion axis
    (ExtrudedDirection) in the solid's local coordinate system — typically
    +Z, which is meaningless on its own. This is transformed into world
    coordinates via the solid's world matrix.

    Handles both direct extrusions (straight pipes/ducts) and extrusions
    nested inside an IfcMappedItem (Revit-exported electrical proxies).

    Args:
        element: IFC element to analyze

    Returns:
        Unit vector [dx, dy, dz] in world coordinates, or None if the element
        has no IfcExtrudedAreaSolid (e.g. fittings stored as IfcFacetedBrep).
    """
    solid = _classify_mep_element(element)
    if solid is None or not solid.is_a("IfcExtrudedAreaSolid"):
        return None

    rot = _solid_world_matrix(element, solid)[:3, :3]
    ext_dir = np.array(solid.ExtrudedDirection.DirectionRatios, dtype=float)
    return _unit(rot @ ext_dir)


def extract_profile_axis(element) -> list[float] | None:
    """
    World-space in-plane X axis of a rectangular MEP element's profile.

    Together with the extrusion direction this fixes the orientation of the
    oriented box that represents a rectangular swept solid. Circular profiles
    are rotationally symmetric and need no such axis.

    Args:
        element: IFC element to analyze

    Returns:
        Unit vector [dx, dy, dz] in world coordinates, or None if the element
        is not a rectangular extrusion.
    """
    solid = _classify_mep_element(element)
    if solid is None or not solid.is_a("IfcExtrudedAreaSolid"):
        return None

    swept = getattr(solid, "SweptArea", None)
    if swept is None or not swept.is_a("IfcRectangleProfileDef"):
        return None

    rot = _solid_world_matrix(element, solid)[:3, :3]
    pos = getattr(swept, "Position", None)
    ref = pos.RefDirection.DirectionRatios if (
        pos and pos.RefDirection) else (1.0, 0.0)
    profile_x = np.array([ref[0], ref[1], 0.0], dtype=float)
    return _unit(rot @ profile_x)


def extract_solid_center(element) -> list[float] | None:
    """
    World-space center of an MEP element's representative swept solid (mm).

    Computed parametrically from the (deepest) IfcExtrudedAreaSolid rather than
    from the tessellated mesh, so shallow companion solids (e.g. faceplates)
    do not skew the result.

    Args:
        element: IFC element to analyze

    Returns:
        [x, y, z] center in millimeters, or None if the element has no
        IfcExtrudedAreaSolid.
    """
    solid = _classify_mep_element(element)
    if solid is None or not solid.is_a("IfcExtrudedAreaSolid"):
        return None

    swept = getattr(solid, "SweptArea", None)
    ext_dir = np.array(solid.ExtrudedDirection.DirectionRatios, dtype=float)
    depth = solid.Depth

    pos = getattr(swept, "Position", None) if swept else None
    ploc = pos.Location.Coordinates if (pos and pos.Location) else (0.0, 0.0)

    local_center = np.array([ploc[0], ploc[1], 0.0]) + (depth / 2.0) * ext_dir
    world_center = _solid_world_matrix(element, solid) @ np.array(
        [*local_center, 1.0])
    return np.round(world_center[:3], 2).tolist()


def swept_solid_aabb(mep: dict) -> tuple[list[float] | None, list[float] | None]:
    """
    World AABB of an MEP element, derived from its swept-solid representation.

    The mechanism is shape-type dependent:
        - cylindrical: exact AABB of the finite cylinder defined by
          (center, direction, radius, length)
        - rectangular: exact AABB of the oriented box defined by
          (center, direction, axisX, sizeX, sizeY, sizeZ)
        - other:       falls back to the stored bbox (bbox_min/bbox_max)

    Args:
        mep: MEP element dict produced by extract_mep_elements

    Returns:
        (bbox_min, bbox_max) in millimeters, or (None, None) if unavailable.
    """
    shape_type = mep.get("shapeType")
    center = mep.get("center")
    direction = mep.get("direction")

    if shape_type == "cylindrical" and center and direction:
        c = np.array(center, dtype=float)
        w = np.array(direction, dtype=float)
        h = (mep.get("length") or 0.0) / 2.0
        r = mep.get("radius") or 0.0
        half = h * np.abs(w) + r * np.sqrt(np.clip(1.0 - w ** 2, 0.0, 1.0))
        return (c - half).round(2).tolist(), (c + half).round(2).tolist()

    if shape_type == "rectangular" and center and direction and mep.get("axisX"):
        c = np.array(center, dtype=float)
        w = np.array(direction, dtype=float)
        u = np.array(mep["axisX"], dtype=float)
        v = np.cross(w, u)
        hu = (mep.get("sizeX") or 0.0) / 2.0
        hv = (mep.get("sizeY") or 0.0) / 2.0
        hw = (mep.get("sizeZ") or 0.0) / 2.0
        half = hu * np.abs(u) + hv * np.abs(v) + hw * np.abs(w)
        return (c - half).round(2).tolist(), (c + half).round(2).tolist()

    return mep.get("bbox_min"), mep.get("bbox_max")
