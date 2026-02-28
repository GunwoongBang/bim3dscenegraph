"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

import ifcopenshell.util.placement
import numpy as np

from . import geometry


# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",            # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Light fixtures and panelboards
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
            - selective geometry fields (populated only for wall-related elements)
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
                "shapeType": None,
                "geomAxis": None,
                "radiusMm": None,
                "penetrationCenter": None,
                "penetrationSizeXmm": None,
                "penetrationSizeYmm": None,
                "penetrationSizeZmm": None,
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


def _upsert_best_edge(edge_map, key, edge):
    """
    Keep the highest-confidence edge for a key.
    """
    current = edge_map.get(key)
    if current is None or edge["confidence"] > current["confidence"]:
        edge_map[key] = edge


def _normalize_vector(vec):
    if not vec:
        return None
    arr = np.array(vec, dtype=float)
    norm = np.linalg.norm(arr)
    if norm == 0:
        return None
    return (arr / norm).round(5).tolist()


def _iter_representation_items(element):
    representation = getattr(element, "Representation", None)
    reps = getattr(representation, "Representations", None)
    if not reps:
        return

    stack = []
    for rep in reps:
        stack.extend(getattr(rep, "Items", []) or [])

    while stack:
        item = stack.pop()
        if item is None:
            continue
        yield item

        if item.is_a("IfcMappedItem"):
            source = getattr(item, "MappingSource", None)
            mapped = getattr(source, "MappedRepresentation",
                             None) if source else None
            stack.extend(getattr(mapped, "Items", []) or [])


def _axis_from_local_placement(element):
    try:
        matrix = ifcopenshell.util.placement.get_local_placement(
            element.ObjectPlacement
        )
        axis = matrix[:3, 0].tolist()
        return _normalize_vector(axis)
    except Exception:
        return None


def _extract_shape_signature(element):
    for item in _iter_representation_items(element):
        if item.is_a("IfcExtrudedAreaSolid"):
            swept = getattr(item, "SweptArea", None)
            if swept and swept.is_a("IfcCircleProfileDef"):
                radius = getattr(swept, "Radius", None)
                return {
                    "shapeType": "cylindrical",
                    "radiusMm": radius,
                    "axis": None,
                }
            if swept and swept.is_a("IfcRectangleProfileDef"):
                return {
                    "shapeType": "rectangular",
                    "radiusMm": None,
                    "axis": None,
                }

    return {
        "shapeType": "other",
        "radiusMm": None,
        "axis": None,
    }


def _bbox_overlap_with_axis(mep_bbox_min, mep_bbox_max, wall_bbox_min, wall_bbox_max, axis):
    if not mep_bbox_min or not mep_bbox_max or not wall_bbox_min or not wall_bbox_max:
        return None

    overlap_min = [max(mep_bbox_min[i], wall_bbox_min[i]) for i in range(3)]
    overlap_max = [min(mep_bbox_max[i], wall_bbox_max[i]) for i in range(3)]

    if any(overlap_min[i] >= overlap_max[i] for i in range(3)):
        return None

    extents = [round(overlap_max[i] - overlap_min[i], 5) for i in range(3)]
    center = [round((overlap_min[i] + overlap_max[i]) / 2, 5)
              for i in range(3)]
    axis_arr = np.array(axis, dtype=float) if axis else None

    if axis_arr is not None:
        penetration_length = float(np.dot(np.abs(axis_arr), np.array(extents)))
    else:
        penetration_length = float(max(extents))

    return {
        "penetrationCenter": center,
        "penetrationLengthMm": round(penetration_length, 5),
        "penetrationSizeXmm": extents[0],
        "penetrationSizeYmm": extents[1],
        "penetrationSizeZmm": extents[2],
    }


def enrich_mep_geometry_for_wall_penetrations(
    mep_model,
    mep_elements,
    mep_wall_edges,
    walls,
    logger=None,
):
    """
    Enrich wall-related MEP elements with representation-based geometry summary.

    Method:
      1) Consider only MEP elements linked to walls via mep_wall_edges
      2) Classify geometry from IFC representation items
      3) Compute penetration metrics from MEP-wall overlap volume

    Args:
        mep_model: ifcopenshell model instance (MEP IFC)
        mep_elements: List of MEP dictionaries (mutated in-place)
        mep_wall_edges: List of MEP-Wall relationship dicts
        walls: List of wall dictionaries
        logger: Optional logger for output messages

    Returns:
        The same mep_elements list with updated geometry fields.
    """
    mep_by_id = {elem["id"]: elem for elem in mep_elements}
    wall_by_id = {wall["id"]: wall for wall in walls}

    related_mep_ids = {edge["mep_id"] for edge in mep_wall_edges}
    wall_ids_by_mep = {}
    for edge in mep_wall_edges:
        wall_ids_by_mep.setdefault(edge["mep_id"], set()).add(edge["wall_id"])

    mep_entities = {}
    for mep_type in MEP_TYPES:
        try:
            entities = mep_model.by_type(mep_type)
        except RuntimeError:
            continue
        for entity in entities:
            mep_entities[entity.GlobalId] = entity

    enriched_count = 0
    for mep_id in related_mep_ids:
        mep_data = mep_by_id.get(mep_id)
        entity = mep_entities.get(mep_id)

        if not mep_data or not entity:
            continue

        signature = _extract_shape_signature(entity)
        axis = signature["axis"] or _axis_from_local_placement(entity)

        mep_data["shapeType"] = signature["shapeType"]
        mep_data["geomAxis"] = axis

        best_overlap = None
        for wall_id in wall_ids_by_mep.get(mep_id, set()):
            wall = wall_by_id.get(wall_id)
            if wall is None:
                continue
            overlap = _bbox_overlap_with_axis(
                mep_data.get("bbox_min"),
                mep_data.get("bbox_max"),
                wall.get("bbox_min"),
                wall.get("bbox_max"),
                axis,
            )
            if overlap is None:
                continue
            if best_overlap is None or overlap["penetrationLengthMm"] > best_overlap["penetrationLengthMm"]:
                best_overlap = overlap

        if best_overlap:
            mep_data["penetrationCenter"] = best_overlap["penetrationCenter"]

            if signature["shapeType"] == "cylindrical":
                mep_data["radiusMm"] = signature["radiusMm"]
                mep_data["penetrationSizeXmm"] = None
                mep_data["penetrationSizeYmm"] = None
                mep_data["penetrationSizeZmm"] = None
            elif signature["shapeType"] == "rectangular":
                mep_data["radiusMm"] = None
                mep_data["penetrationSizeXmm"] = best_overlap["penetrationSizeXmm"]
                mep_data["penetrationSizeYmm"] = best_overlap["penetrationSizeYmm"]
                mep_data["penetrationSizeZmm"] = best_overlap["penetrationSizeZmm"]
            else:
                mep_data["radiusMm"] = None
                mep_data["penetrationSizeXmm"] = None
                mep_data["penetrationSizeYmm"] = None
                mep_data["penetrationSizeZmm"] = None
        else:
            mep_data["radiusMm"] = None
            mep_data["penetrationCenter"] = None
            mep_data["penetrationSizeXmm"] = None
            mep_data["penetrationSizeYmm"] = None
            mep_data["penetrationSizeZmm"] = None

        enriched_count += 1

    if logger:
        logger.logText(
            "BIM2GRAPH",
            f"{enriched_count} wall-related MEP elements enriched with geometry summary"
        )

    return mep_elements


def compute_mep_wall_relationships(
    mep_model,
    mep_elements,
    walls,
    allow_geometry_fallback=True,
    logger=None
):
    """
    Compute relationships between MEP elements and walls.

    Priority:
        1. IFC topology (IfcRelConnectsElements, IfcRelVoidsElement + IfcRelFillsElement)
        2. Geometry fallback (AABB intersection), only if enabled

    Args:
        mep_model: ifcopenshell model instance (MEP IFC)
        mep_elements: List of MEP dictionaries (from extract_mep_elements)
        walls: List of wall dictionaries (from extract_walls)
        allow_geometry_fallback: Use bbox overlap only when topology did not produce an edge
        logger: Optional logger for output messages

    Returns:
        List of relationship dictionaries with keys:
            - mep_id: MEP element GlobalId
            - wall_id: Wall GlobalId
            - relationship: "PASSES_THROUGH"
            - source: "ifc_topology" or "geom_bbox_overlap"
            - confidence: float in [0, 1]
    """
    mep_ids = {elem["id"] for elem in mep_elements}
    wall_ids = {wall["id"] for wall in walls}
    edge_map = {}
    topology_count = 0
    geometry_count = 0

    def _add_topology_edge(mep_id, wall_id):
        nonlocal topology_count
        key = (mep_id, wall_id)
        prev = edge_map.get(key)
        _upsert_best_edge(edge_map, key, {
            "mep_id": mep_id,
            "wall_id": wall_id,
            "relationship": "PASSES_THROUGH",
            "source": "ifc_topology",
            "confidence": 1.0,
        })
        if prev is None:
            topology_count += 1

    # IFC topology: direct element connection
    for rel in mep_model.by_type("IfcRelConnectsElements"):
        rel_elem = getattr(rel, "RelatingElement", None)
        rld_elem = getattr(rel, "RelatedElement", None)
        if not rel_elem or not rld_elem:
            continue

        rel_id = getattr(rel_elem, "GlobalId", None)
        rld_id = getattr(rld_elem, "GlobalId", None)
        rel_is_wall = rel_elem.is_a("IfcWall")
        rld_is_wall = rld_elem.is_a("IfcWall")

        if rel_id in mep_ids and rld_is_wall and rld_id in wall_ids:
            _add_topology_edge(rel_id, rld_id)
        elif rld_id in mep_ids and rel_is_wall and rel_id in wall_ids:
            _add_topology_edge(rld_id, rel_id)

    # IFC topology: opening in wall filled by MEP element
    opening_to_wall = {}
    for rel in mep_model.by_type("IfcRelVoidsElement"):
        wall = getattr(rel, "RelatingBuildingElement", None)
        opening = getattr(rel, "RelatedOpeningElement", None)
        if not wall or not opening:
            continue
        wall_id = getattr(wall, "GlobalId", None)
        opening_id = getattr(opening, "GlobalId", None)
        if wall_id in wall_ids and opening_id:
            opening_to_wall[opening_id] = wall_id

    for rel in mep_model.by_type("IfcRelFillsElement"):
        opening = getattr(rel, "RelatingOpeningElement", None)
        elem = getattr(rel, "RelatedBuildingElement", None)
        if not opening or not elem:
            continue
        mep_id = getattr(elem, "GlobalId", None)
        opening_id = getattr(opening, "GlobalId", None)
        wall_id = opening_to_wall.get(opening_id)
        if mep_id in mep_ids and wall_id:
            _add_topology_edge(mep_id, wall_id)

    if allow_geometry_fallback:
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

                if not bbox_intersects(
                    mep_bbox_min, mep_bbox_max, wall_bbox_min, wall_bbox_max
                ):
                    continue

                key = (mep["id"], wall["id"])
                if key in edge_map:
                    continue
                edge_map[key] = {
                    "mep_id": mep["id"],
                    "wall_id": wall["id"],
                    "relationship": "PASSES_THROUGH",
                    "source": "geom_bbox_overlap",
                    "confidence": 0.4,
                }
                geometry_count += 1

    relationships = [
        edge_map[key] for key in sorted(edge_map.keys())
    ]

    if logger:
        logger.logText(
            "BIM2GRAPH",
            f"{len(relationships)} MEP-wall edges "
            f"(topology={topology_count}, geometry_fallback={geometry_count})"
        )

    return relationships


def compute_mep_system_parent_edges(
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
        bbox = geometry.extract_bbox(space)
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
