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

    return "POSITIVE" if dot > 0 else "NEGATIVE"
