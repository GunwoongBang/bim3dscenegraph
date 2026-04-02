import numpy as np
import ifcopenshell.util.placement


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",           # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Switches, receptacles, panelboards
]


def _normalize(vec):
    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return None
    return arr / norm


def _generate_orientation_matrix(mapped_item):
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


def _classify_mep_element(element):
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


def extract_shape_signature(element):
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


def _generate_rotation_matrix_from_axis(position):
    if position is None:
        return np.eye(3)

    axis = getattr(position, "Axis", None)
    ref_dir = getattr(position, "RefDirection", None)

    z = np.array(getattr(axis, "DirectionRatios",
                 (0.0, 0.0, 1.0)), dtype=float)
    x = np.array(getattr(ref_dir, "DirectionRatios",
                 (1.0, 0.0, 0.0)), dtype=float)

    z = _normalize(z)
    x = _normalize(x)
    if z is None or x is None:
        return np.eye(3)

    y = _normalize(np.cross(z, x))
    if y is None:
        return np.eye(3)

    x = _normalize(np.cross(y, z))
    if x is None:
        return np.eye(3)

    return np.column_stack((x, y, z))


def extract_extrusion_axis(element):
    item, mapped_rot = _classify_mep_element(element)
    if item is None or not item.is_a("IfcExtrudedAreaSolid"):
        return None

    extruded_dir = getattr(item, "ExtrudedDirection", None)
    direction = getattr(extruded_dir, "DirectionRatios", None)
    if not direction:
        return None

    local_dir = _normalize(direction)
    if local_dir is None:
        return None

    item_pos = getattr(item, "Position", None)
    item_rot = _generate_rotation_matrix_from_axis(item_pos)

    try:
        elem_matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
        elem_rot = elem_matrix[:3, :3]
    except Exception:
        elem_rot = np.eye(3)

    world_dir = elem_rot @ mapped_rot @ item_rot @ local_dir
    world_dir = _normalize(world_dir)
    if world_dir is None:
        return None

    return np.round(world_dir, 5).tolist()
