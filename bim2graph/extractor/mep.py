"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

import ifcopenshell.util.placement
import numpy as np

from .geometry import extract_centroid, extract_bbox


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",           # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Light fixtures, electric receptacles, panelboards
]


def extract_mep_systems(model, logger=None):
    """
    Extract MEP systems from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        systems:
        List of system dictionaries with keys:
            - id: GlobalId
            - name: System name
            - ifcClass: IFC class type
    """
    systems = []

    for system in model.by_type("IfcSystem"):
        systems.append({
            "id": system.GlobalId,
            "name": getattr(system, "Name", None) or "Unknown",
            "ifcClass": system.is_a(),
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(systems)} MEP systems extracted")

    return systems


def enrice_mep_for_wall_penetrations():
    return []


def extract_mep_elements(arc_model, mep_model, logger=None):
    """
    Extract MEP elements from the IFC model.

    Args:
        arc_model: ifcopenshell model instance (Architectural IFC)
        mep_model: ifcopenshell model instance (MEP IFC)
        logger: Optional logger for output messages

    Returns:
        mep_elements:
        List of MEP element dictionaries with keys:
            - id: GlobalId
            - name: Element name
            - ifcClass: IFC class type
            - center: [x, y, z] geometric center in mm
            - bbox_min, bbox_max: Bounding box in mm
            - selective geometry fields (populated only for wall-related elements)
    """
    mep_elements = []

    for mep_type in MEP_TYPES:
        try:
            elements = mep_model.by_type(mep_type)
        except RuntimeError:
            continue

        for elem in elements:
            center = extract_centroid(elem)
            bbox = extract_bbox(elem)

            if center is None:
                if logger:
                    logger.logText(
                        "BIM2GRAPH", f"Geometry extraction failed for MEP {elem.GlobalId}")
                continue

            # mep_

            mep_elements.append({
                "id": elem.GlobalId,
                "name": getattr(elem, "Name", None) or "Unknown",
                "ifcClass": elem.is_a(),
                "center": center,
                "bbox_min": bbox[0] if bbox else None,
                "bbox_max": bbox[1] if bbox else None,
                "shapeType": None,
                "geomAxis": None,
                "radiusMm": None,
                "penetrationCenter": None,
                "penetrationLengthMm": None,
                "penetrationSizeXmm": None,
                "penetrationSizeYmm": None,
                "penetrationSizeZmm": None,
            })

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
        bool:
        True if boxes intersect
    """
    for i in range(3):
        if bbox1_max[i] < bbox2_min[i]:
            return False
        if bbox2_max[i] < bbox1_min[i]:
            return False
    return True


def compute_mep_wall_relationships(
    mep_elements,
    walls,
    logger=None
):
    """
    Compute relationships between MEP elements and walls.

    Priority:
        Geometry fallback (AABB intersection)

    Args:
        mep_model: ifcopenshell model instance (MEP IFC)
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        walls: List of wall dictionaries (from extract_walls)
        allow_geometry_fallback: Use bbox overlap only when topology did not produce an edge
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

            if not bbox_intersects(mep_bbox_min, mep_bbox_max, wall_bbox_min, wall_bbox_max):
                continue

            edges.append({
                "mep_id": mep["id"],
                "wall_id": wall["id"],
                "relationship": "PASSES_THROUGH",
            })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(edges)} MEPElement-wall relationships extracted")

    return edges


def compute_mep_system_space_edges(
    arc_model,
    mep_model,
    systems,
    memberships,
    mep_elements,
    logger=None,
):
    """
    Compute MEP system-to-space relationships based on topology.

    A system is connected to spaces if any of its member elements are in that space.
    Uses IFC topology (IfcRelContainedInSpatialStructure, IfcRelReferencedInSpatialStructure)
    with geometry fallback for unmapped elements.

    Methodology (priority order):
      1. IFC topology through IfcRelContainedInSpatialStructure / IfcRelReferencedInSpatialStructure
      2. Geometry fallback using MEP-space bounding-box intersection

    Args:
        arc_model: ifcopenshell model instance for the ARC file
        mep_model: ifcopenshell model instance for the MEP file
        systems: List of system dictionaries (from extract_mep_systems)
        memberships: List of system membership dicts (from extract_mep_system_memberships)
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        logger: Optional logger for output messages

    Returns:
        List of system-space edge dictionaries with keys:
            - system_id
            - space_id
            - source
            - confidence
    """
    mep_by_id = {elem["id"]: elem for elem in mep_elements}
    system_to_meps = {}
    for edge in memberships:
        system_to_meps.setdefault(edge["system_id"], set()).add(edge["mep_id"])

    # mep_id -> {space_id: {"source": ..., "confidence": ...}}
    mep_to_spaces = {}
    topology_count = 0
    geometry_count = 0

    def _add_mep_space(mep_id, space_id, source, confidence):
        nonlocal topology_count, geometry_count
        current = mep_to_spaces.setdefault(mep_id, {}).get(space_id)
        if current is not None and current["confidence"] >= confidence:
            return

        if current is None:
            if source == "ifc_topology":
                topology_count += 1
            elif source == "geom_bbox_overlap":
                geometry_count += 1

        mep_to_spaces.setdefault(mep_id, {})[space_id] = {
            "source": source,
            "confidence": confidence,
        }

    def _collect_space_relation(relating_structure, related_elements):
        if not relating_structure or not relating_structure.is_a("IfcSpace"):
            return
        space_id = relating_structure.GlobalId
        for obj in related_elements or []:
            obj_id = getattr(obj, "GlobalId", None)
            if obj_id in mep_by_id:
                _add_mep_space(obj_id, space_id, "ifc_topology", 1.0)

    # Read topology from both files so split ARC/MEP exports are covered.
    for model in (arc_model, mep_model):
        if model is None:
            continue
        for rel in model.by_type("IfcRelContainedInSpatialStructure"):
            _collect_space_relation(
                getattr(rel, "RelatingStructure", None),
                getattr(rel, "RelatedElements", []),
            )
        for rel in model.by_type("IfcRelReferencedInSpatialStructure"):
            _collect_space_relation(
                getattr(rel, "RelatingStructure", None),
                getattr(rel, "RelatedElements", []),
            )

    # Geometry fallback for MEP elements not mapped by topology.
    space_bboxes = {}
    for space in arc_model.by_type("IfcSpace"):
        bbox = extract_bbox(space)
        if bbox:
            space_bboxes[space.GlobalId] = bbox

    for mep_id, mep in mep_by_id.items():
        if mep_id in mep_to_spaces:
            continue

        mep_bbox_min = mep.get("bbox_min")
        mep_bbox_max = mep.get("bbox_max")
        if not mep_bbox_min or not mep_bbox_max:
            continue

        for space_id, (space_bbox_min, space_bbox_max) in space_bboxes.items():
            if bbox_intersects(
                mep_bbox_min, mep_bbox_max, space_bbox_min, space_bbox_max
            ):
                _add_mep_space(mep_id, space_id, "geom_bbox_overlap", 0.4)

    system_space_edges = []
    for system in systems:
        system_id = system["id"]
        mep_ids = system_to_meps.get(system_id, set())
        space_edges_by_id = {}

        for mep_id in mep_ids:
            for space_id, meta in mep_to_spaces.get(mep_id, {}).items():
                current = space_edges_by_id.get(space_id)
                if current is None or meta["confidence"] > current["confidence"]:
                    space_edges_by_id[space_id] = meta

        for space_id in sorted(space_edges_by_id.keys()):
            meta = space_edges_by_id[space_id]
            system_space_edges.append({
                "system_id": system_id,
                "space_id": space_id,
                "source": meta["source"],
                "confidence": meta["confidence"],
            })

    if logger:
        logger.logText(
            "BIM2GRAPH",
            f"{len(system_space_edges)} MEP system-space edges "
            f"(topology={topology_count}, geometry_fallback={geometry_count})"
        )

    return system_space_edges
