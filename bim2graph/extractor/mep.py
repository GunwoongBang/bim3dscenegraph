"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

from . import geometry


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",       # Pipes
    "IfcBuildingElementProxy",  # Light fixtures (receptacles, switches)
]


def extract_mep_elements(model, logger=None):
    """
    Extract MEP elements from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        List of MEP element dictionaries with keys:
            - id: GlobalId
            - name: Element name
            - ifcClass: IFC class type
            - objectType: Object type description
            - center: [x, y, z] geometric center in mm
            - bbox_min, bbox_max: Bounding box in mm
    """
    mep_elements = []

    for mep_type in MEP_TYPES:
        try:
            elements = model.by_type(mep_type)
        except RuntimeError:
            # Type not in schema (IFC2X3 vs IFC4)
            continue

        for elem in elements:
            center = geometry.extract_centroid(elem)
            bbox = geometry.extract_bbox(elem)

            if center is None:
                if logger:
                    logger.logText(
                        "BIM2GRAPH",
                        f"Geometry extraction failed for MEP {elem.GlobalId}"
                    )
                continue

            mep_data = {
                "id": elem.GlobalId,
                "name": getattr(elem, "Name", None) or "Unknown",
                "ifcClass": elem.is_a(),
                "objectType": getattr(elem, "ObjectType", None),
                "center": center,
                "bbox_min": bbox[0] if bbox else None,
                "bbox_max": bbox[1] if bbox else None,
            }
            mep_elements.append(mep_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(mep_elements)} MEP elements extracted")

    return mep_elements


def bbox_intersects(bbox1_min, bbox1_max, bbox2_min, bbox2_max, tolerance=0):
    """
    Check if two axis-aligned bounding boxes intersect.

    Args:
        bbox1_min, bbox1_max: First bounding box corners [x, y, z]
        bbox2_min, bbox2_max: Second bounding box corners [x, y, z]
        tolerance: Expansion of boxes for near-miss detection (mm)

    Returns:
        True if boxes intersect (or are within tolerance)
    """
    for i in range(3):
        if bbox1_max[i] < bbox2_min[i]:
            return False
        if bbox2_max[i] < bbox1_min[i]:
            return False
    return True


def compute_mep_wall_relationships(mep_elements, walls, logger=None):
    """
    Compute relationships between MEP elements and walls based on geometry.

    An MEP element is related to a wall if:
    1. Their bounding boxes intersect (MEP passes through wall)
    2. Or MEP is within tolerance distance of wall (MEP is near wall surface)

    Args:
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        List of relationship dictionaries with keys:
            - mep_id: MEP element GlobalId
            - wall_id: Wall GlobalId
            - relationship: "PASSES_THROUGH"
    """
    relationships = []

    for mep in mep_elements:
        mep_bbox_min = mep.get("bbox_min")
        mep_bbox_max = mep.get("bbox_max")

        if not mep_bbox_min or not mep_bbox_max:
            continue

        for wall in walls:
            wall_bbox_min = wall.get("bbox_min")
            wall_bbox_max = wall.get("bbox_max")

            if not wall_bbox_min or not wall_bbox_max:
                continue

            # Check for direct intersection
            if bbox_intersects(mep_bbox_min, mep_bbox_max,
                               wall_bbox_min, wall_bbox_max, tolerance=0):
                relationships.append({
                    "mep_id": mep["id"],
                    "wall_id": wall["id"],
                    "relationship": "PASSES_THROUGH"
                })

    return relationships
