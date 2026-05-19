"""
Relationship extraction from IFC models (space-wall boundaries, etc.).
"""

from .util import (
    compute_space_side_of_wall,
    check_bbox_intersection,
    compute_bbox_overlap,
)


def compute_wall_opening_rels(arc_model, logger=None) -> list[dict]:
    """
    Extract Wall-Opening edges from IfcRelVoidsElement.

    Args:
        arc_model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        edges:
        List of dictionaries with keys:
            - wall_id: Wall GlobalId
            - opening_id: Opening GlobalId
    """
    edges = []

    for rel in arc_model.by_type("IfcRelVoidsElement"):
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
            "BIM2GRAPH", f"Computed {len(edges)} Wall-Opening relationships")
    return edges


def compute_space_wall_rels(arc_model, spaces: list[dict], walls: list[dict], logger=None) -> list[dict]:
    """
    Extract space-wall topological relationships with side information.

    The 'side' property indicates which side of the wall's AXIS2 the space is on,
    enabling queries to determine the correct layer order from any space.

    When querying layers from a space:
        - If side == wall.directionSense: reverse layer order
        - If side != wall.directionSense: use IFC layer order

    Args:
        arc_model: ifcopenshell model instance
        spaces: List of space dictionaries (from extract_spaces)
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        edges:
        List of edge dictionaries with keys:
            - space_id: Space GlobalId
            - wall_id: Wall GlobalId
            - side: "POSITIVE" or "NEGATIVE"
            - boundaryType: "INTERNAL", "EXTERNAL", etc.
    """
    edges = []
    exiting_pairs = set()

    # Build lookup dicts
    space_centroids = {
        s["id"]: s.get("centroid") for s in spaces
    }
    wall_geometry = {
        w["id"]: (w.get("center"), w.get("axis2")) for w in walls
    }

    for rel in arc_model.by_type("IfcRelSpaceBoundary"):
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

        pair = (space_id, wall_id)
        if pair in exiting_pairs:
            continue
        exiting_pairs.add(pair)

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
            "BIM2GRAPH", f"Computed {len(edges)} Space-Wall relationships")

    return edges


def compute_mep_memberships(mep_model, mep_elements: list[dict], logger=None) -> list[dict]:
    """
    Extract MEP memberships (MEPSystem-MEPElement edges) from IfcRelAssignsToGroup.

    Args:
        mep_model: ifcopenshell model instance
        mep_elements: List of extracted MEP element dictionaries
        logger: Optional logger for output messages

    Returns:
        edges:
        List of membership dictionaries with keys:
            - mep_system_id: System GlobalId
            - mep_element_id: MEP element GlobalId
    """
    mep_ids = {elem["id"] for elem in mep_elements}
    membership_pairs = set()

    for rel in mep_model.by_type("IfcRelAssignsToGroup"):
        system = getattr(rel, "RelatingGroup", None)
        rel_id = getattr(system, "GlobalId", None)

        if not system or not system.is_a("IfcSystem"):
            continue

        for obj in getattr(rel, "RelatedObjects", []):
            obj_id = getattr(obj, "GlobalId", None)

            if not rel_id or not obj_id:
                continue
            if obj_id not in mep_ids:
                continue

            membership_pairs.add((rel_id, obj_id))

    memberships = [
        {"mep_system_id": mep_system_id, "mep_element_id": mep_element_id}
        for mep_system_id, mep_element_id in sorted(membership_pairs)
    ]

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Computed {len(memberships)} MEP memberships")

    return memberships


def compute_mep_element_wall_rels(mep_elements: list[dict], walls: list[dict], logger=None) -> list[dict]:
    """
    Compute relationships between MEP elements and walls.

    Priority:
        Geometry fallback (AABB intersection)

    Args:
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        edges:
        List of relationship dictionaries with keys:
            - mep_element_id: MEP element GlobalId
            - wall_id: Wall GlobalId
            - relationship: "PASSES_THROUGH"
    """
    edges = []

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

            if not check_bbox_intersection(mep_bbox_min, mep_bbox_max, wall_bbox_min, wall_bbox_max):
                continue

            overlap = compute_bbox_overlap(
                mep_bbox_min,
                mep_bbox_max,
                wall_bbox_min,
                wall_bbox_max,
            )
            if overlap is None:
                continue

            shape_type = mep.get("shapeType")
            edge_data = {
                "mep_element_id": mep["id"],
                "wall_id": wall["id"],
                "relationship": "PASSES_THROUGH",
                "source": "geom_bbox_overlap",
                "penetrationCenter": overlap["penetrationCenter"],
                "radiusMm": None,
                "penetrationLengthMm": None,
                "penetrationSizeXmm": None,
                "penetrationSizeYmm": None,
                "penetrationSizeZmm": None,
            }

            if shape_type == "cylindrical":
                edge_data["radiusMm"] = mep.get("radiusMm")
                edge_data["penetrationLengthMm"] = round(max(
                    overlap["penetrationSizeXmm"],
                    overlap["penetrationSizeYmm"],
                    overlap["penetrationSizeZmm"],
                ), 5)
            elif shape_type == "rectangular":
                edge_data["penetrationSizeXmm"] = overlap["penetrationSizeXmm"]
                edge_data["penetrationSizeYmm"] = overlap["penetrationSizeYmm"]
                edge_data["penetrationSizeZmm"] = overlap["penetrationSizeZmm"]

            edges.append(edge_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Computed {len(edges)} MEPElement-Wall relationships")

    return edges


def compute_mep_element_space_rels(mep_elements: list[dict], spaces: list[dict], logger=None) -> list[dict]:
    """
    Compute MEPElement-Space relationships via AABB intersection.

    A MEP element is considered visible in a space if their bounding boxes
    intersect.

    Args:
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        spaces: List of space dictionaries (from extract_spaces)
        logger: Optional logger for output messages

    Returns:
        edges:
        List of edge dictionaries with keys:
            - mep_element_id: MEP element GlobalId
            - space_id: Space GlobalId
    """
    edges = []

    for mep in mep_elements:
        mep_bbox_min = mep.get("bbox_min")
        mep_bbox_max = mep.get("bbox_max")
        if not mep_bbox_min or not mep_bbox_max:
            continue

        for space in spaces:
            space_bbox_min = space.get("bbox_min")
            space_bbox_max = space.get("bbox_max")
            if not space_bbox_min or not space_bbox_max:
                continue

            if not check_bbox_intersection(
                mep_bbox_min, mep_bbox_max, space_bbox_min, space_bbox_max
            ):
                continue

            edges.append({
                "mep_element_id": mep["id"],
                "space_id": space["id"],
            })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Computed {len(edges)} MEPElement-Space relationships")

    return edges
