"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

from . import geometry


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",       # Pipes
    "IfcBuildingElementProxy",  # Light fixtures (receptacles, switches)
]


def extract_mep_systems(model, logger=None):
    """
    Extract MEP systems from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        List of system dictionaries with keys:
            - id: GlobalId
            - name: System name
            - ifcClass: IFC class type
            - objectType: Object type description
    """
    systems = []

    for system in model.by_type("IfcSystem"):
        systems.append({
            "id": system.GlobalId,
            "name": getattr(system, "Name", None) or "Unknown",
            "ifcClass": system.is_a(),
            "objectType": getattr(system, "ObjectType", None),
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(systems)} MEP systems extracted")

    return systems


def extract_mep_system_memberships(model, mep_elements, logger=None):
    """
    Extract MEP system memberships from IfcRelAssignsToGroup.

    Args:
        model: ifcopenshell model instance
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        logger: Optional logger for output messages

    Returns:
        List of membership dictionaries with keys:
            - system_id: System GlobalId
            - mep_id: MEP element GlobalId
    """
    mep_ids = {elem["id"] for elem in mep_elements}
    memberships = set()

    for rel in model.by_type("IfcRelAssignsToGroup"):
        system = getattr(rel, "RelatingGroup", None)
        if not system or not system.is_a("IfcSystem"):
            continue

        for obj in getattr(rel, "RelatedObjects", []):
            obj_id = getattr(obj, "GlobalId", None)
            if obj_id in mep_ids:
                memberships.add((system.GlobalId, obj_id))

    edges = [
        {"system_id": system_id, "mep_id": mep_id}
        for system_id, mep_id in sorted(memberships)
    ]

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(edges)} MEP system memberships extracted")

    return edges


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


def bbox_intersects(bbox1_min, bbox1_max, bbox2_min, bbox2_max):
    """
    Check if two axis-aligned bounding boxes intersect.

    Args:
        bbox1_min, bbox1_max: First bounding box corners [x, y, z]
        bbox2_min, bbox2_max: Second bounding box corners [x, y, z]

    Returns:
        True if boxes intersect
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

    An MEP element is related to a wall if their bounding boxes intersect (MEP passes through wall)

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
                               wall_bbox_min, wall_bbox_max):
                relationships.append({
                    "mep_id": mep["id"],
                    "wall_id": wall["id"],
                    "relationship": "PASSES_THROUGH"
                })

    return relationships


def compute_mep_system_parent_edges(
    arc_model,
    systems,
    memberships,
    mep_elements,
    mep_wall_edges,
    logger=None,
):
    """
    Compute parent MEP system edges to spaces (if visible) or to walls.

    A system is connected to spaces if any of its elements intersect a space.
    Otherwise, it is connected to walls based on its elements' wall edges.

    Args:
        arc_model: ifcopenshell model instance for the ARC file
        systems: List of system dictionaries (from extract_mep_systems)
        memberships: List of system membership dicts (from extract_mep_system_memberships)
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        mep_wall_edges: List of MEP-Wall relationships (from compute_mep_wall_relationships)
        logger: Optional logger for output messages

    Returns:
        Tuple (system_space_edges, system_wall_edges)
    """
    mep_by_id = {elem["id"]: elem for elem in mep_elements}
    system_to_meps = {}
    for edge in memberships:
        system_to_meps.setdefault(edge["system_id"], set()).add(edge["mep_id"])

    space_bboxes = {}
    for space in arc_model.by_type("IfcSpace"):
        bbox = geometry.extract_bbox(space)
        if bbox:
            space_bboxes[space.GlobalId] = bbox

    mep_to_spaces = {}
    for mep_id, mep in mep_by_id.items():
        mep_bbox_min = mep.get("bbox_min")
        mep_bbox_max = mep.get("bbox_max")
        if not mep_bbox_min or not mep_bbox_max:
            continue

        for space_id, (space_bbox_min, space_bbox_max) in space_bboxes.items():
            if bbox_intersects(mep_bbox_min, mep_bbox_max,
                               space_bbox_min, space_bbox_max):
                mep_to_spaces.setdefault(mep_id, set()).add(space_id)

    mep_to_walls = {}
    for edge in mep_wall_edges:
        mep_to_walls.setdefault(edge["mep_id"], set()).add(edge["wall_id"])

    system_space_edges = []
    system_wall_edges = []

    for system in systems:
        system_id = system["id"]
        mep_ids = system_to_meps.get(system_id, set())

        space_ids = set()
        for mep_id in mep_ids:
            space_ids.update(mep_to_spaces.get(mep_id, set()))

        if space_ids:
            for space_id in sorted(space_ids):
                system_space_edges.append({
                    "system_id": system_id,
                    "space_id": space_id,
                })
        else:
            wall_ids = set()
            for mep_id in mep_ids:
                wall_ids.update(mep_to_walls.get(mep_id, set()))

            for wall_id in sorted(wall_ids):
                system_wall_edges.append({
                    "system_id": system_id,
                    "wall_id": wall_id,
                })

    if logger:
        logger.logText(
            "BIM2GRAPH",
            f"{len(system_space_edges)} MEP system-space edges, "
            f"{len(system_wall_edges)} MEP system-wall edges created",
        )

    return system_space_edges, system_wall_edges
