"""
Relationship extraction from IFC models (space-wall boundaries, etc.).
"""


from .utils.rel_utils import compute_space_side_of_wall


def ccompute_space_wall_edges(model, spaces, walls, logger=None):
    """
    Extract space-wall topological relationships with side information.

    The 'side' property indicates which side of the wall's AXIS2 the space is on,
    enabling queries to determine the correct layer order from any space.

    When querying layers from a space:
        - If side == wall.directionSense: reverse layer order
        - If side != wall.directionSense: use IFC layer order

    Args:
        model: ifcopenshell model instance
        spaces: List of space dictionaries (from extract_spaces)
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        List of edge dictionaries with keys:
            - space_id: Space GlobalId
            - wall_id: Wall GlobalId
            - side: "POSITIVE" or "NEGATIVE"
            - boundaryType: "INTERNAL", "EXTERNAL", etc.
    """
    edges = []

    # Build lookup dicts
    space_centroids = {
        s["id"]: s.get("centroid") for s in spaces
    }
    wall_geometry = {
        w["id"]: (w.get("center"), w.get("axis2")) for w in walls
    }

    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = getattr(rel, "RelatingSpace", None)
        element = getattr(rel, "RelatedBuildingElement", None)

        if not space or not element:
            continue
        if not space.is_a("IfcSpace"):
            continue
        if not element.is_a("IfcWall"):
            continue

        space_id = space.GlobalId
        wall_id = element.GlobalId

        # Compute which side of the wall this space is on
        space_centroid = space_centroids.get(space_id)
        wall_center, wall_axis2 = wall_geometry.get(wall_id)

        side = compute_space_side_of_wall(
            space_centroid, wall_center, wall_axis2)

        # Get boundary type (internal/external)
        # boundary_type = getattr(rel, "InternalOrExternalBoundary", None)

        edges.append({
            "space_id": space_id,
            "wall_id": wall_id,
            "side": side,
            # "boundaryType": str(boundary_type) if boundary_type else None
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(edges)} Space-Wall relationships extracted")

    return edges


def compute_wall_opening_edges(model, walls, logger=None):
    """
    Extract Wall-Opening edges from IfcRelVoidsElement.

    Args:
        model: ifcopenshell model instance
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        wall_opening_edges:
        List of dictionaries with keys:
            - wall_id: Wall GlobalId
            - opening_id: Opening GlobalId
    """
    edges = []

    for rel in model.by_type("IfcRelVoidsElement"):
        wall = getattr(rel, "RelatingBuildingElement", None)
        opening = getattr(rel, "RelatedOpeningElement", None)

        if not wall or not opening:
            continue
        if not wall.is_a("IfcWall"):
            continue
        if not opening.is_a("IfcOpeningElement"):
            continue

        wall_id = getattr(wall, "GlobalId", None)
        opening_id = getattr(opening, "GlobalId", None)
        if not wall_id or not opening_id:
            continue

        edges.append({
            "wall_id": wall_id,
            "opening_id": opening_id
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(edges)} Wall-Opening relationships extracted")
    return edges


def compute_mep_memberships(model, logger=None):
    """
    Extract MEP memberships (MEPSystem-MEPElement edges) from IfcRelAssignsToGroup.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        edges:
        List of membership dictionaries with keys:
            - system_id: System GlobalId
            - mep_id: MEP element GlobalId
    """
    memberships = []

    for rel in model.by_type("IfcRelAssignsToGroup"):
        system = getattr(rel, "RelatingGroup", None)
        rel_id = getattr(system, "GlobalId", None)

        if not system or not system.is_a("IfcSystem"):
            continue

        for obj in getattr(rel, "RelatedObjects", []):
            obj_id = getattr(obj, "GlobalId", None)

            if not rel_id or not obj_id:
                continue

            memberships.append({
                "system_id": rel_id,
                "mep_id": obj_id
            })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(memberships)} MEP memberships (MEPSystem-MEPElement) extracted")

    return memberships
