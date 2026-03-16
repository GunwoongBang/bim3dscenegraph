import numpy as np


def extract_ifc_color(materials):
    """
    Extract [r, g, b] from IFC geometry materials if available.

    Args:
        materials: IfcOpenShell geometry material collection

    Returns:
        list[float] in [0, 1] range, or None when unavailable
    """
    if not materials:
        return None

    try:
        mat = materials[0]
        col = mat.get_color() if hasattr(
            mat, "get_color") else getattr(mat, "diffuse", None)
        if col is None:
            return None

        r = float(col.r())
        g = float(col.g())
        b = float(col.b())
        return [max(0.0, min(1.0, r)), max(0.0, min(1.0, g)), max(0.0, min(1.0, b))]
    except Exception:
        return None


def face_normal(vertices, face):
    """
    Compute the outward normal of a triangular face.

    Args:
        vertices: numpy array of shape (N, 3)
        face: index triple (i0, i1, i2)

    Returns:
        unit normal vector or None for degenerate faces
    """
    v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]
    n = np.cross(v1 - v0, v2 - v0)
    norm = np.linalg.norm(n)
    if norm < 1e-10:
        return None
    return n / norm


def sample_points_on_mesh(vertices, faces, points_per_m2=100, building_bbox=None):
    """
    Sample points uniformly on mesh surface using barycentric coordinates.

    If building_bbox is provided, faces whose normal points outward (i.e.
    projecting along the normal exits the building bbox) are skipped.
    This correctly keeps BOTH faces of interior walls while filtering the
    outer face of exterior walls.

    Args:
        vertices: numpy array of shape (N, 3) - mesh vertices
        faces: numpy array of shape (M, 3) - triangle face indices
        points_per_m2: sampling density (points per square meter)
        building_bbox: optional tuple (bbox_min, bbox_max) numpy arrays [x,y,z];
            faces that project outside this box are treated as exterior and skipped.

    Returns:
        points: numpy array of shape (P, 3) - sampled point cloud
    """
    all_points = []

    if building_bbox is not None:
        bbox_min, bbox_max = building_bbox
        # Step distance: 10% of the smallest building dimension.
        # This is unit-agnostic and ensures step > wall thickness but < room size.
        step = float(np.min(bbox_max - bbox_min)) * 0.1

    for face in faces:
        if building_bbox is not None:
            normal = face_normal(vertices, face)
            if normal is not None:
                face_center = (
                    vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
                projected = face_center + normal * step
                # If projecting outward exits the building bbox, this is an
                # exterior-facing surface — skip it.
                outside = any(
                    projected[i] < bbox_min[i] or projected[i] > bbox_max[i]
                    for i in range(3)
                )
                if outside:
                    continue
        # Get triangle vertices
        v0, v1, v2 = vertices[face[0]], vertices[face[1]], vertices[face[2]]

        # Compute triangle area using cross product
        edge1 = v1 - v0
        edge2 = v2 - v0
        area = 0.5 * np.linalg.norm(np.cross(edge1, edge2))

        if area < 1e-10:  # Skip degenerate triangles
            continue

        # Number of points to sample based on area
        n_points = max(1, int(area * points_per_m2))

        # Sample using barycentric coordinates
        # Generate random barycentric coordinates
        r1 = np.random.random(n_points)
        r2 = np.random.random(n_points)

        # Ensure points are inside triangle (not outside)
        mask = r1 + r2 > 1
        r1[mask] = 1 - r1[mask]
        r2[mask] = 1 - r2[mask]

        # Convert barycentric to cartesian
        # P = (1 - r1 - r2) * v0 + r1 * v1 + r2 * v2
        points = (1 - r1 - r2)[:, np.newaxis] * v0 + \
            r1[:, np.newaxis] * v1 + \
            r2[:, np.newaxis] * v2

        all_points.append(points)

    if not all_points:
        return np.array([]).reshape(0, 3)

    return np.vstack(all_points)


def transform_point_cloud(points, translation=(0, 0, 0), yaw_degrees=0):
    """
    Apply translation and yaw rotation to a point cloud.

    Args:
        points: numpy array of shape (N, 3) - point coordinates
        translation: tuple (x, y, z) - translation in meters
        yaw_degrees: float - rotation around Z-axis in degrees

    Returns:
        transformed_points: numpy array of shape (N, 3)
    """
    # Convert yaw to radians
    yaw_rad = np.radians(yaw_degrees)

    # Rotation matrix around Z-axis (yaw)
    cos_yaw = np.cos(yaw_rad)
    sin_yaw = np.sin(yaw_rad)
    rotation_matrix = np.array([
        [cos_yaw, -sin_yaw, 0],
        [sin_yaw, cos_yaw, 0],
        [0, 0, 1]
    ])

    # Apply rotation first, then translation
    rotated_points = points @ rotation_matrix.T
    translated_points = rotated_points + np.array(translation)

    return translated_points
