"""
Opening element extraction from IFC models.
"""

from .geometry import extract_centroid


def extract_openings(model, logger=None):
    """
    Extract opening nodes from IfcOpeningElement entities.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        openings:
        List of opening dictionaries with keys:
            - id: Opening GlobalId
            - name: Opening name
            - ifcClass: IFC class type
            - center: [x, y, z] centroid in mm
    """
    openings = []

    for opening in model.by_type("IfcOpeningElement"):
        opening_data = {
            "id": opening.GlobalId,
            "name": getattr(opening, "Name", None) or "Unknown",
            "ifcClass": opening.is_a(),
            "center": extract_centroid(opening),
        }
        openings.append(opening_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(openings)} Opening elements extracted")

    return openings
