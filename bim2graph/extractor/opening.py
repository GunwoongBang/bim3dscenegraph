"""
Opening element extraction from IFC models.
"""

from .geometry import extract_centroid


def extract_openings(model, logger=None) -> list[dict]:
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

    ifc_openings = model.by_type("IfcOpeningElement")

    if not ifc_openings:
        if logger:
            logger.logText(
                "BIM2GRAPH", "No IfcOpeningElement entities found in model")

        return openings

    for opening in ifc_openings:
        opening_data = {
            "id": opening.GlobalId,
            "name": getattr(opening, "Name", None) or "Unknown",
            "ifcClass": opening.is_a(),
            "center": extract_centroid(opening),
        }
        openings.append(opening_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(openings)} Opening elements")

    return openings
