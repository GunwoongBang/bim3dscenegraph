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
        side:
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

    side = "POSITIVE" if dot > 0 else "NEGATIVE"

    return side


def check_bbox_intersection(bbox1_min, bbox1_max, bbox2_min, bbox2_max):
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


def compute_bbox_overlap(bbox1_min, bbox1_max, bbox2_min, bbox2_max) -> dict | None:
    """
    Return overlap center/size geometry, or None if no intersection.

    Args:
        bbox1_min, bbox1_max: First bounding box corners [x, y, z]
        bbox2_min, bbox2_max: Second bounding box corners [x, y, z]

    Returns:
        dict: Dictionary with overlap geometry or None if no intersection
    """
    if not check_bbox_intersection(bbox1_min, bbox1_max, bbox2_min, bbox2_max):
        return None

    overlap_min = [max(bbox1_min[i], bbox2_min[i]) for i in range(3)]
    overlap_max = [min(bbox1_max[i], bbox2_max[i]) for i in range(3)]
    overlap_size = [round(overlap_max[i] - overlap_min[i], 5)
                    for i in range(3)]
    overlap_center = [round((overlap_min[i] + overlap_max[i]) / 2, 5)
                      for i in range(3)]

    return {
        "penetrationCenter": overlap_center,
        "penetrationSizeXmm": overlap_size[0],
        "penetrationSizeYmm": overlap_size[1],
        "penetrationSizeZmm": overlap_size[2],
    }


def estimate_wall_thickness_mm(wall_bbox_min, wall_bbox_max, wall_axis2=None):
    """
    Estimate wall thickness in mm from wall bbox and optional local AXIS2.

    Args:
        wall_bbox_min, wall_bbox_max: Wall bounding box corners [x, y, z]
        wall_axis2: Optional wall local AXIS2 direction vector [dx, dy, dz]

    Returns:
        thicknessMm: Estimated wall thickness in mm, or None if cannot be estimated
    """
    if not wall_bbox_min or not wall_bbox_max:
        return None

    extents = np.array([
        wall_bbox_max[i] - wall_bbox_min[i] for i in range(3)
    ], dtype=float)

    if wall_axis2:
        axis = np.array(wall_axis2, dtype=float)
        norm = np.linalg.norm(axis)
        if norm > 0:
            axis = axis / norm
            return round(float(np.dot(np.abs(axis), extents)), 5)

    return round(float(np.min(extents)), 5)
