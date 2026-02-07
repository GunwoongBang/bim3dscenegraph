"""
Relationship extraction from IFC models (space-wall boundaries, etc.).
"""

import numpy as np


def compute_space_side_of_wall(space_centroid, wall_center, wall_axis2):
    """
    Determine which side of the wall's AXIS2 the space is on.

    Uses dot product of the vector from wall center to space centroid
    with the wall's AXIS2 direction to determine the side.

    Args:
        space_centroid: [x, y, z] coordinates of space centroid in mm
        wall_center: [x, y, z] coordinates of wall geometric center in mm
        wall_axis2: [dx, dy, dz] direction vector of wall's AXIS2

    Returns:
        "POSITIVE" if space is on positive side of AXIS2
        "NEGATIVE" if space is on negative side of AXIS2
        None if any input is missing
    """
    if not space_centroid or not wall_center or not wall_axis2:
        return None

    # Vector from wall center to space centroid
    v = np.array(space_centroid) - np.array(wall_center)

    # Dot product determines which side
    dot = np.dot(v, np.array(wall_axis2))

    return "POSITIVE" if dot > 0 else "NEGATIVE"


def extract_space_wall_edges(model, spaces, walls, logger=None):
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
    space_centroids = {s["id"]: s.get("centroid") for s in spaces}
    wall_geometry = {
        w["id"]: (w.get("center"), w.get("axis2"))
        for w in walls
    }

    for rel in model.by_type("IfcRelSpaceBoundary"):
        space = getattr(rel, "RelatingSpace", None)
        element = getattr(rel, "RelatedBuildingElement", None)

        if not space or not element:
            continue

        if not element.is_a("IfcWall"):
            continue

        space_id = space.GlobalId
        wall_id = element.GlobalId

        # Compute which side of the wall this space is on
        space_centroid = space_centroids.get(space_id)
        wall_center, wall_axis2 = wall_geometry.get(wall_id, (None, None))
        side = compute_space_side_of_wall(
            space_centroid, wall_center, wall_axis2)

        # Get boundary type (internal/external)
        boundary_type = getattr(rel, "InternalOrExternalBoundary", None)

        edges.append({
            "space_id": space_id,
            "wall_id": wall_id,
            "side": side,
            "boundaryType": str(boundary_type) if boundary_type else None
        })

    return edges
