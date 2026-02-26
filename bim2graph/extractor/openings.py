"""
Opening extraction and wall-opening relationship extraction from IFC models.
"""

from . import geometry


def extract_openings_and_edges(model, walls, logger=None):
    """
    Extract opening nodes and Wall-Opening edges from IfcRelVoidsElement.

    Args:
        model: ifcopenshell model instance
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        Tuple (openings, wall_opening_edges):
            openings: List of opening dictionaries with keys:
                - id: Opening GlobalId
                - name: Opening name
                - ifcClass: IFC class type
                - center: [x, y, z] centroid in mm
            wall_opening_edges: List of dictionaries with keys:
                - wall_id: Wall GlobalId
                - opening_id: Opening GlobalId
    """
    wall_ids = {wall["id"] for wall in walls}
    openings_by_id = {}
    wall_opening_pairs = set()

    def ensure_opening_node(opening_obj=None, opening_id=None):
        oid = opening_id or (
            getattr(opening_obj, "GlobalId", None) if opening_obj else None)
        if not oid or oid in openings_by_id:
            return oid

        opening_entity = opening_obj
        if opening_entity is None:
            try:
                opening_entity = model.by_guid(oid)
            except Exception:
                opening_entity = None

        if opening_entity is not None:
            openings_by_id[oid] = {
                "id": oid,
                "name": getattr(opening_entity, "Name", None) or "Unknown",
                "ifcClass": opening_entity.is_a(),
                "center": geometry.extract_centroid(opening_entity),
            }
        else:
            openings_by_id[oid] = {
                "id": oid,
                "name": "Unknown",
                "ifcClass": "IfcOpeningElement",
                "center": None,
            }

        return oid

    for rel in model.by_type("IfcRelVoidsElement"):
        wall = getattr(rel, "RelatingBuildingElement", None)
        opening = getattr(rel, "RelatedOpeningElement", None)

        if not wall or not opening:
            continue
        if not wall.is_a("IfcWall"):
            continue

        wall_id = getattr(wall, "GlobalId", None)
        opening_id = ensure_opening_node(opening_obj=opening)
        if not wall_id or not opening_id:
            continue
        if wall_id not in wall_ids:
            continue

        wall_opening_pairs.add((wall_id, opening_id))

    openings = [openings_by_id[key] for key in sorted(openings_by_id.keys())]
    wall_opening_edges = sorted(wall_opening_pairs)
    wall_opening_edges = [
        {"wall_id": wall_id, "opening_id": opening_id}
        for wall_id, opening_id in wall_opening_edges
    ]

    if logger:
        logger.logText(
            "BIM2GRAPH",
            f"{len(openings)} Opening elements, "
            f"{len(wall_opening_edges)} Wall-Opening relationships extracted"
        )

    return openings, wall_opening_edges
