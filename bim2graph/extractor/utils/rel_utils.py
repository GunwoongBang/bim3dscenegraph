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
