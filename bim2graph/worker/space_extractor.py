"""
Space extraction from IFC models.
"""

from .util import extract_centroid, extract_bbox


def extract_spaces(arc_model, logger=None) -> list[dict]:
    """
    Extract all spaces from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        spaces:
        List of space dictionaries with keys:
            - id: GlobalId
            - name: Space name
            - longName: Long name (if available)
            - ifcClass: IFC class type
            - centroid: [x, y, z] in millimeters
            - bbox_min, bbox_max: AABB in millimeters
    """
    spaces = []

    ifc_spaces = arc_model.by_type("IfcSpace")

    if not ifc_spaces:
        if logger:
            logger.logText("BIM2GRAPH", "No IfcSpace entities found in model")

        return spaces

    for space in ifc_spaces:
        center = extract_centroid(space)
        bbox_min, bbox_max = extract_bbox(space)

        space_data = {
            "id": space.GlobalId,
            "longName": getattr(space, "LongName", None),
            "name": getattr(space, "Name", None),
            "ifcClass": space.is_a(),
            "centroid": center,
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
        }
        spaces.append(space_data)

    if logger:
        logger.logText("BIM2GRAPH", f"Extracted {len(spaces)} Space elements")

    return spaces
