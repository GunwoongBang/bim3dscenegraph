"""
Spatial structure extraction (Building, Storey) from IFC models.
"""

from .util import aabb_union, aabb_center


def extract_buildings(arc_model, storeys: list[dict], building_storey_rels: list[dict], logger=None) -> list[dict]:
    """
    Extract all buildings from the IFC model.

    Each building is given a center point derived from the axis-aligned
    bounding box enclosing all of its (retained) storeys.

    Args:
        arc_model: ifcopenshell model instance
        storeys: List of retained storey dictionaries (from extract_storeys)
        building_storey_rels: Building-Storey edges (from compute_building_storey_rels)
        logger: Optional logger for output messages

    Returns:
        List of building dictionaries with keys:
            - id: GlobalId
            - ifcClass: IFC class type
            - center: [x, y, z] center point in millimeters, or None
    """
    storey_bbox = {
        s["id"]: (s.get("bbox_min"), s.get("bbox_max")) for s in storeys
    }

    # building_id -> list of retained storey bounding boxes
    building_storeys: dict[str, list] = {}
    for rel in building_storey_rels:
        bbox = storey_bbox.get(rel["storey_id"])
        if bbox is None:
            # Storey was skipped (no rooms) -> ignore
            continue
        building_storeys.setdefault(rel["building_id"], []).append(bbox)

    buildings = []
    for b in arc_model.by_type("IfcBuilding"):
        bbox_min, bbox_max = aabb_union(building_storeys.get(b.GlobalId, []))
        buildings.append({
            "id": b.GlobalId,
            "ifcClass": b.is_a(),
            "center": aabb_center(bbox_min, bbox_max),
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(buildings)} Building elements")

    return buildings


def extract_storeys(arc_model, spaces: list[dict], storey_space_rels: list[dict], logger=None) -> list[dict]:
    """
    Extract building storeys that contain at least one space (room).

    Storeys without any HAS_SPACE relationship are skipped entirely, so they
    are never loaded into Neo4j. Each retained storey is given a center point
    derived from the axis-aligned bounding box enclosing its spaces.

    Args:
        arc_model: ifcopenshell model instance
        spaces: List of space dictionaries (from extract_spaces)
        storey_space_rels: Storey-Space edges (from compute_storey_space_rels)
        logger: Optional logger for output messages

    Returns:
        List of storey dictionaries with keys:
            - id: GlobalId
            - ifcClass: IFC class type
            - center: [x, y, z] center point in millimeters
            - bbox_min, bbox_max: aggregate AABB of contained spaces in mm
    """
    space_bbox = {
        s["id"]: (s.get("bbox_min"), s.get("bbox_max")) for s in spaces
    }

    # storey_id -> list of contained space bounding boxes
    storey_spaces: dict[str, list] = {}
    for rel in storey_space_rels:
        storey_spaces.setdefault(rel["storey_id"], []).append(
            space_bbox.get(rel["space_id"]))

    storeys = []
    for s in arc_model.by_type("IfcBuildingStorey"):
        bboxes = storey_spaces.get(s.GlobalId)
        if not bboxes:
            # No HAS_SPACE relationship with any room -> do not load
            continue

        bbox_min, bbox_max = aabb_union(bboxes)
        storeys.append({
            "id": s.GlobalId,
            "ifcClass": s.is_a(),
            "center": aabb_center(bbox_min, bbox_max),
            "bbox_min": bbox_min,
            "bbox_max": bbox_max,
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(storeys)} Storey elements with rooms")

    return storeys
