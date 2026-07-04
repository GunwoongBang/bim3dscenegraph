"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

from .util import (
    MEP_TYPES,
    extract_bbox,
    extract_shape_signature,
    extract_centroid,
    extract_shape_dimensions,
    extract_extruded_direction,
    extract_profile_axis,
    extract_solid_center,
)


def extract_mep_systems(mep_model, logger=None) -> list[dict]:
    """
    Extract MEP systems from the IFC model.

    Args:
        mep_model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        mep_systems:
        List of system dictionaries with keys:
            - id: GlobalId
            - name: System name
            - ifcClass: IFC class type
    """
    mep_systems = []

    ifc_systems = mep_model.by_type("IfcSystem")

    if not ifc_systems:
        if logger:
            logger.logText("BIM2GRAPH", "No IfcSystem entities found in model")

        return mep_systems

    for system in ifc_systems:
        mep_systems.append({
            "id": system.GlobalId,
            "name": getattr(system, "Name", None) or "Unknown",
            "ifcClass": system.is_a(),
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(mep_systems)} MEP systems")

    return mep_systems


def extract_mep_elements(mep_model, logger=None) -> list[dict]:
    """
    Extract MEP elements from the IFC model.

    Args:
        mep_model: ifcopenshell model instance (MEP IFC)
        logger: Optional logger for output messages

    Returns:
        mep_elements:
        List of MEP element dictionaries with keys:
            - id: GlobalId
            - name: Element name
            - ifcClass: IFC class type
            - shapeType: "cylindrical", "rectangular", or "other"
            - center: solid center [x, y, z] in mm (parametric swept-solid
              center for cyl/rect, mesh centroid for other)
            - direction: Extrusion direction unit vector [dx, dy, dz] in world
              coords (None for elements without an extrusion, e.g. fittings)
            - radius, length: cylindrical dims in mm (None otherwise)
            - sizeX, sizeY, sizeZ, axisX: rectangular oriented-box dims + world
              in-plane X axis (None otherwise)
            - bbox_min, bbox_max: AABB in mm, only for "other" (None for
              cyl/rect, which are reconstructed from their swept solid)
    """
    mep_elements = []

    for mep_type in MEP_TYPES:

        elements = mep_model.by_type(mep_type)

        if not elements:
            if logger:
                logger.logText(
                    "BIM2GRAPH", f"No {mep_type} entities found in MEP model")

            continue

        for element in elements:
            shape_type = extract_shape_signature(element)
            dims = extract_shape_dimensions(element)
            direction = extract_extruded_direction(element)

            # cyl/rect are represented by their swept solid: parametric center
            # and an on-demand AABB. "other" keeps the tessellated bbox as its
            # only geometric descriptor.
            if shape_type == "other":
                center = extract_centroid(element)
                bbox_min, bbox_max = extract_bbox(element)
                axis_x = None
            else:
                center = extract_solid_center(element)
                bbox_min, bbox_max = None, None
                axis_x = extract_profile_axis(element)

            mep_data = {
                "id": element.GlobalId,
                "name": getattr(element, "Name", None),
                "ifcClass": element.is_a(),
                "shapeType": shape_type,
                "center": center,
                "direction": direction,
                "radius": dims.get("radius"),
                "length": dims.get("length"),
                "sizeX": dims.get("sizeX"),
                "sizeY": dims.get("sizeY"),
                "sizeZ": dims.get("sizeZ"),
                "axisX": axis_x,
                "bbox_min": bbox_min,
                "bbox_max": bbox_max,
            }

            mep_elements.append(mep_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(mep_elements)} MEP elements")

    return mep_elements
