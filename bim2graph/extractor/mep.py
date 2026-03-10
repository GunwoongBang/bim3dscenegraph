"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

import numpy as np

from .utils.mep_utils import MEP_TYPES, extract_shape_signature, extract_extrusion_axis, compute_ray_wall_penetration
from .geometry import extract_centroid, extract_bbox, extract_placement


def extract_mep_systems(model, logger=None) -> list[dict]:
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
            "BIM2GRAPH", f"Extracted {len(systems)} MEP systems")

    return systems


def extract_mep_elements(arc_model, mep_model, logger=None) -> list[dict]:
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
    wall_geometries = []

    for wall in arc_model.by_type("IfcWall"):
        wall_bbox = extract_bbox(wall)

        if not wall_bbox:
            continue

        _, axis = extract_placement(wall)
        wall_geometries.append({
            "id": wall.GlobalId,
            "bbox_min": wall_bbox[0],
            "bbox_max": wall_bbox[1],
            "axis2": axis,
        })

    for mep_type in MEP_TYPES:
        try:
            elements = mep_model.by_type(mep_type)
        except RuntimeError:
            continue

        for element in elements:
            center = extract_centroid(element)
            bbox = extract_bbox(element)

            if center is None:
                if logger:
                    logger.logText(
                        "BIM2GRAPH", f"Geometry extraction failed for MEP {element.GlobalId}")
                continue

            signature = extract_shape_signature(element)
            axis = extract_extrusion_axis(element)

            best_overlap = None
            if center and axis:
                for wall in wall_geometries:
                    wall_normal = wall.get("axis2")
                    if wall_normal and abs(np.dot(np.array(axis), np.array(wall_normal))) < 0.3:
                        continue
                    hit = compute_ray_wall_penetration(center, axis, wall)
                    if hit is None:
                        continue
                    if (best_overlap is None or
                            hit["penetrationLengthMm"] > best_overlap["penetrationLengthMm"]):
                        best_overlap = hit

            mep_data = {
                "id": element.GlobalId,
                "name": getattr(element, "Name", None),
                "ifcClass": element.is_a(),
                "bbox_min": bbox[0] if bbox else None,
                "bbox_max": bbox[1] if bbox else None,
                "shapeType": signature["shapeType"],
                "geomAxis": axis,  # For MEP elements, the vector is along the extrusion direction
                "radiusMm": None,
                "penetrationCenter": None,
                "penetrationLengthMm": None,
                "penetrationSizeXmm": None,
                "penetrationSizeYmm": None,
                "penetrationSizeZmm": None,
            }

            if best_overlap:
                mep_data["penetrationCenter"] = best_overlap["penetrationCenter"]
                mep_data["penetrationLengthMm"] = best_overlap["penetrationLengthMm"]
                if signature["shapeType"] == "cylindrical":
                    mep_data["radiusMm"] = signature["radiusMm"]
                elif signature["shapeType"] == "rectangular":
                    mep_data["penetrationSizeXmm"] = signature.get("xDimMm")
                    mep_data["penetrationSizeYmm"] = signature.get("yDimMm")
                    mep_data["penetrationSizeZmm"] = best_overlap["penetrationLengthMm"]

            mep_elements.append(mep_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(mep_elements)} MEP elements")

    return mep_elements
