"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

from .util import (
    MEP_TYPES,
    extract_shape_signature,
    extract_bbox,
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
            - bbox_min, bbox_max: Bounding box in mm
            - selective geometry fields (populated only for wall-related elements)
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
            bbox = extract_bbox(element)

            signature = extract_shape_signature(element)
            mep_data = {
                "id": element.GlobalId,
                "name": getattr(element, "Name", None),
                "ifcClass": element.is_a(),
                "bbox_min": bbox[0] if bbox else None,
                "bbox_max": bbox[1] if bbox else None,
                "shapeType": signature["shapeType"],
                "radiusMm": signature.get("radiusMm"),
            }

            mep_elements.append(mep_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(mep_elements)} MEP elements")

    return mep_elements
