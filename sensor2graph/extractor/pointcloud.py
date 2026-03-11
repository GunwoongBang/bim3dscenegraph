"""
Point cloud generation from IFC model.
"""

import numpy as np
import open3d as o3d
from . import geometry

# Color palette for different elements (RGB, 0-1 range)
ELEMENT_COLORS = [
    [0.8, 0.2, 0.2],  # Red
    [0.2, 0.8, 0.2],  # Green
    [0.2, 0.2, 0.8],  # Blue
    [0.8, 0.8, 0.2],  # Yellow
    [0.8, 0.2, 0.8],  # Magenta
    [0.2, 0.8, 0.8],  # Cyan
    [0.9, 0.5, 0.2],  # Orange
    [0.5, 0.2, 0.9],  # Purple
]


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


def _face_normal(vertices, face):
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


def sample_points_on_mesh(vertices, faces, points_per_m2=100, interior_point=None):
    """
    Sample points uniformly on mesh surface using barycentric coordinates.

    If interior_point is provided, only faces whose normal points toward that
    point are sampled (indoor-surface-only mode).

    Args:
        vertices: numpy array of shape (N, 3) - mesh vertices
        faces: numpy array of shape (M, 3) - triangle face indices
        points_per_m2: sampling density (points per square meter)
        interior_point: optional [x, y, z] reference point inside the building;
            faces whose normal points away from it are skipped.

    Returns:
        points: numpy array of shape (P, 3) - sampled point cloud
    """
    all_points = []

    for face in faces:
        if interior_point is not None:
            normal = _face_normal(vertices, face)
            if normal is not None:
                face_center = (vertices[face[0]] + vertices[face[1]] + vertices[face[2]]) / 3.0
                to_interior = np.array(interior_point) - face_center
                # Skip face if normal points away from the interior
                if np.dot(normal, to_interior) < 0:
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


def _compute_interior_point(model, element_types):
    """
    Estimate a building interior reference point as the centroid of all
    element mesh centroids for the given element types.

    Args:
        model: ifcopenshell model instance
        element_types: list of IFC class strings

    Returns:
        interior_point: numpy array [x, y, z] or None if no geometry found
    """
    settings = geometry.get_geom_settings()
    centroids = []
    for et in element_types:
        for element in model.by_type(et):
            try:
                vertices, _ = geometry.extract_mesh_from_shape(element)
                centroids.append(vertices.mean(axis=0))
            except Exception:
                pass
    if not centroids:
        return None
    return np.mean(centroids, axis=0)


def generate_point_cloud(model, element_types=None, points_per_m2=100,
                         translation=(0, 0, 0), yaw_degrees=0,
                         indoor_only=True, logger=None):
    """
    Generate a point cloud from the mesh surfaces of specified IFC element types.

    Args: 
        model: ifcopenshell model instance
        element_types: List of IFC element types to include in the point cloud
        points_per_m2: Sampling density (number of points per square meter)
        translation: tuple (x, y, z) - translation in meters
        yaw_degrees: float - rotation around Z-axis in degrees
        indoor_only: if True, only sample faces whose normals face the building
            interior (simulates an indoor sensor that cannot see outer surfaces)
        logger: Optional logger for output messages

    Returns:
        combined_pcd: Open3D point cloud with all points and colors
    """
    if element_types is None:
        element_types = ["IfcWall", "IfcSlab"]

    interior_point = None
    if indoor_only:
        interior_point = _compute_interior_point(model, element_types)
        if logger:
            logger.logText(
                "SENSOR2GRAPH",
                f"Indoor-only mode: interior reference point = {np.round(interior_point, 2) if interior_point is not None else None}"
            )

    point_clouds = {}
    all_points = []
    all_colors = []
    color_idx = 0
    total_points = 0

    for element_type in element_types:
        elements = model.by_type(element_type)

        for element in elements:
            try:
                vertices, faces = geometry.extract_mesh_from_shape(element)

                # Sample points on mesh surface (indoor faces only if interior_point is set)
                points = sample_points_on_mesh(vertices, faces, points_per_m2, interior_point)

                # Assign color for this element
                color = ELEMENT_COLORS[color_idx % len(ELEMENT_COLORS)]
                colors = np.tile(color, (len(points), 1))
                color_idx += 1

                point_clouds[element.GlobalId] = {
                    'points': points,
                    'colors': colors,
                    'element_type': element_type,
                    'name': element.Name or "Unnamed"
                }

                all_points.append(points)
                all_colors.append(colors)
                total_points += len(points)

                if logger:
                    logger.logText(
                        "SENSOR2GRAPH",
                        f"Sampled {len(points)} points from {element_type} {element.GlobalId}"
                    )

            except Exception as e:
                if logger:
                    logger.logText(
                        "SENSOR2GRAPH",
                        f"Failed to process {element.GlobalId}: {e}"
                    )

    # Combine all points and colors
    if all_points:
        combined_points = np.vstack(all_points)
        combined_colors = np.vstack(all_colors)

        # Apply transformation (translation + yaw rotation)
        if translation != (0, 0, 0) or yaw_degrees != 0:
            combined_points = transform_point_cloud(
                combined_points, translation, yaw_degrees
            )
            if logger:
                logger.logText(
                    "SENSOR2GRAPH",
                    f"Applied transform: translation={translation}, yaw={yaw_degrees}°"
                )

        # Create Open3D point cloud with colors
        combined_pcd = o3d.geometry.PointCloud()
        combined_pcd.points = o3d.utility.Vector3dVector(combined_points)
        combined_pcd.colors = o3d.utility.Vector3dVector(combined_colors)
    else:
        combined_pcd = o3d.geometry.PointCloud()

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            f"Total: {total_points} points from {len(point_clouds)} elements"
        )

    return combined_pcd
