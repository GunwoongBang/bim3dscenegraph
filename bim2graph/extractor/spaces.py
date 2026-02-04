"""
Space extraction from IFC models.
"""

from . import geometry


def extract_spaces(model, logger=None):
    """
    Extract all spaces from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        List of space dictionaries with keys:
            - id: GlobalId
            - name: Space name
            - longName: Long name (if available)
            - ifcClass: IFC class type
            - centroid: [x, y, z] in millimeters
    """
    spaces = []

    for space in model.by_type("IfcSpace"):
        centroid = geometry.extract_centroid(space)

        if centroid is None and logger:
            logger.logText(
                "BIM2GRAPH",
                f"Centroid extraction failed for space {space.GlobalId}"
            )

        space_data = {
            "id": space.GlobalId,
            "name": getattr(space, "Name", None) or "Unknown",
            "longName": getattr(space, "LongName", None),
            "ifcClass": space.is_a(),
            "centroid": centroid
        }
        spaces.append(space_data)

    if logger:
        logger.logText("BIM2GRAPH", f"{len(spaces)} Space elements extracted")

    return spaces
