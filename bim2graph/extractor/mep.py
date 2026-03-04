"""
MEP (Mechanical, Electrical, Plumbing) element extraction from IFC models.
"""

import numpy as np

from bim2graph.extractor.utils.mep_utils import extract_shape_signature

from .utils.mep_utils import MEP_TYPES
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

        _, wall_axis2 = extract_placement(wall)
        wall_geometries.append({
            "id": wall.GlobalId,
            "bbox_min": wall_bbox[0],
            "bbox_max": wall_bbox[1],
            "axis2": wall_axis2,
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
            _, axis = extract_placement(element)

            # best_overlap = None

            # if bbox:
            #     for wall in wall_geometries:
            #         overlap = _bbox_overlap_with_axis(
            #             bbox[0],
            #             bbox[1],
            #             wall.get("bbox_min"),
            #             wall.get("bbox_max"),
            #             axis,
            #         )
            #         if overlap is None:
            #             continue

            #         wall_thickness = _estimate_wall_thickness_mm(wall)

            #         if wall_thickness is not None:
            #             overlap["penetrationLengthMm"] = wall_thickness

            #         if (best_overlap is None or
            #                 overlap["penetrationLengthMm"] > best_overlap["penetrationLengthMm"]):
            #             best_overlap = overlap

            mep_data = {
                "id": element.GlobalId,
                "name": getattr(element, "Name", None) or "Unknown",
                "ifcClass": element.is_a(),
                "bbox_min": bbox[0] if bbox else None,
                "bbox_max": bbox[1] if bbox else None,
                "shapeType": signature["shapeType"],
                "geomAxis": axis,
                "radiusMm": None,
                "penetrationCenter": None,
                "penetrationLengthMm": None,
                "penetrationSizeXmm": None,
                "penetrationSizeYmm": None,
                "penetrationSizeZmm": None,
            }

            # if best_overlap:
            #     mep_data["penetrationCenter"] = best_overlap["penetrationCenter"]
            #     mep_data["penetrationLengthMm"] = best_overlap["penetrationLengthMm"]

            #     if signature["shapeType"] == "cylindrical":
            #         mep_data["radiusMm"] = signature["radiusMm"]
            #     elif signature["shapeType"] == "rectangular":
            #         mep_data["penetrationSizeXmm"] = best_overlap["penetrationSizeXmm"]
            #         mep_data["penetrationSizeYmm"] = best_overlap["penetrationSizeYmm"]
            #         mep_data["penetrationSizeZmm"] = best_overlap["penetrationSizeZmm"]

            mep_elements.append(mep_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(mep_elements)} MEP elements")

    return mep_elements


# def _bbox_overlap_with_axis(mep_bbox_min, mep_bbox_max, wall_bbox_min, wall_bbox_max, axis):
#     if not mep_bbox_min or not mep_bbox_max or not wall_bbox_min or not wall_bbox_max:
#         return None

#     overlap_min = [max(mep_bbox_min[i], wall_bbox_min[i]) for i in range(3)]
#     overlap_max = [min(mep_bbox_max[i], wall_bbox_max[i]) for i in range(3)]

#     if any(overlap_min[i] >= overlap_max[i] for i in range(3)):
#         return None

#     extents = [round(overlap_max[i] - overlap_min[i], 5) for i in range(3)]
#     center = [round((overlap_min[i] + overlap_max[i]) / 2, 5)
#               for i in range(3)]
#     axis_arr = np.array(axis, dtype=float) if axis else None

#     if axis_arr is not None:
#         penetration_length = float(np.dot(np.abs(axis_arr), np.array(extents)))
#     else:
#         penetration_length = float(max(extents))

#     return {
#         "penetrationCenter": center,
#         "penetrationLengthMm": round(penetration_length, 5),
#         "penetrationSizeXmm": extents[0],
#         "penetrationSizeYmm": extents[1],
#         "penetrationSizeZmm": extents[2],
#     }


# def _estimate_wall_thickness_mm(wall):
#     wall_bbox_min = wall.get("bbox_min") if wall else None
#     wall_bbox_max = wall.get("bbox_max") if wall else None
#     if not wall_bbox_min or not wall_bbox_max:
#         return None

#     wall_extents = np.array([
#         wall_bbox_max[i] - wall_bbox_min[i] for i in range(3)
#     ], dtype=float)

#     wall_axis2 = wall.get("axis2") if wall else None
#     if wall_axis2:
#         thickness = float(np.dot(np.abs(np.array(wall_axis2)), wall_extents))
#         return round(thickness, 5)

#     return round(float(min(wall_extents)), 5)
