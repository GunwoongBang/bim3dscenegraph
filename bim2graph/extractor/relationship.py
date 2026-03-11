"""
Relationship extraction from IFC models (space-wall boundaries, etc.).
"""

from .utils.rel_util import (
    compute_space_side_of_wall,
    check_bbox_intersection,
    compute_bbox_overlap,
)
from .geometry import extract_bbox


def compute_space_wall_rels(model, spaces, walls, logger=None) -> list[dict]:
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


def compute_wall_opening_rels(model, logger=None) -> list[dict]:
    """
    Extract Wall-Opening edges from IfcRelVoidsElement.

    Args:
        model: ifcopenshell model instance
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
            "BIM2GRAPH", f"Computed {len(edges)} Wall-Opening relationships")
    return edges


def compute_mep_memberships(model, mep_elements, logger=None) -> list[dict]:
    """
    Extract MEP memberships (MEPSystem-MEPElement edges) from IfcRelAssignsToGroup.

    Args:
        model: ifcopenshell model instance
        mep_elements: List of extracted MEP element dictionaries
        logger: Optional logger for output messages

    Returns:
        edges:
        List of membership dictionaries with keys:
            - system_id: System GlobalId
            - mep_id: MEP element GlobalId
    """
    mep_ids = {elem["id"] for elem in mep_elements}
    membership_pairs = set()

    for rel in model.by_type("IfcRelAssignsToGroup"):
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
        {"system_id": system_id, "mep_id": mep_id}
        for system_id, mep_id in sorted(membership_pairs)
    ]

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Computed {len(memberships)} MEP memberships")

    return memberships


def compute_mep_element_wall_rels(
    mep_elements,
    walls,
    logger=None
) -> list[dict]:
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
            - mep_id: MEP element GlobalId
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
                "mep_id": mep["id"],
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


def compute_mep_system_space_rels(
    arc_model,
    systems,
    memberships,
    mep_elements,
    logger=None,
) -> list[dict]:
    """
    Compute MEP system-to-space relationships using geometry only.

    A system is connected to spaces if any of its member elements are in that space.
    For separated ARC/MEP files, explicit IFC topology between systems/elements
    and ARC spaces is typically unavailable, so relationships are inferred from
    MEP-space bounding-box intersection.

    Args:
        arc_model: ifcopenshell model instance for the ARC file
        systems: List of system dictionaries (from extract_mep_systems)
        memberships: List of system membership dicts (from extract_mep_system_memberships)
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        logger: Optional logger for output messages

    Returns:
        List of system-space edge dictionaries with keys:
            - system_id
            - space_id
            - source
    """
    mep_by_id = {elem["id"]: elem for elem in mep_elements}
    system_to_meps = {}
    for edge in memberships:
        system_to_meps.setdefault(edge["system_id"], set()).add(edge["mep_id"])

    # mep_id -> {space_id: {"source": ...}}
    mep_to_spaces = {}

    def _add_mep_space(mep_id, space_id, source):
        current = mep_to_spaces.setdefault(mep_id, {}).get(space_id)
        if current is not None:
            return

        mep_to_spaces.setdefault(mep_id, {})[space_id] = {
            "source": source,
        }

    # Geometry-only mapping for separated ARC/MEP files.
    space_bboxes = {}
    for space in arc_model.by_type("IfcSpace"):
        bbox = extract_bbox(space)
        if bbox:
            space_bboxes[space.GlobalId] = bbox

    for mep_id, mep in mep_by_id.items():
        mep_bbox_min = mep.get("bbox_min")
        mep_bbox_max = mep.get("bbox_max")
        if not mep_bbox_min or not mep_bbox_max:
            continue

        for space_id, (space_bbox_min, space_bbox_max) in space_bboxes.items():
            if check_bbox_intersection(
                mep_bbox_min, mep_bbox_max, space_bbox_min, space_bbox_max
            ):
                _add_mep_space(mep_id, space_id, "geom_bbox_overlap")

    system_space_edges = []
    for system in systems:
        system_id = system["id"]
        mep_ids = system_to_meps.get(system_id, set())
        space_edges_by_id = {}

        for mep_id in mep_ids:
            for space_id, meta in mep_to_spaces.get(mep_id, {}).items():
                current = space_edges_by_id.get(space_id)
                if current is None:
                    space_edges_by_id[space_id] = meta

        for space_id in sorted(space_edges_by_id.keys()):
            meta = space_edges_by_id[space_id]
            system_space_edges.append({
                "system_id": system_id,
                "space_id": space_id,
                "source": meta["source"],
            })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Computed {len(system_space_edges)} MEPSystem-Space relationships")

    return system_space_edges
