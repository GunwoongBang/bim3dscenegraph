"""
Point cloud generation from IFC model.
"""

import numpy as np
from . import geometry


def sample_points_on_mesh(vertices, faces, points_per_m2=100):
    """
    Sample points uniformly on mesh surface using barycentric coordinates.

    Args:
        vertices: numpy array of shape (N, 3) - mesh vertices
        faces: numpy array of shape (M, 3) - triangle face indices
        points_per_m2: sampling density (points per square meter)

    Returns:
        points: numpy array of shape (P, 3) - sampled point cloud
    """
    all_points = []

    for face in faces:
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


def generate_point_cloud(model, element_types=None, points_per_m2=100, logger=None):
    """
    Generate a point cloud from the mesh surfaces of specified IFC element types.

    Args: 
        model: ifcopenshell model instance
        element_types: List of IFC element types to include in the point cloud
        points_per_m2: Sampling density (number of points per square meter)
        logger: Optional logger for output messages

    Returns:
        List of point cloud dictionaries
    """
    if element_types is None:
        element_types = ["IfcWall", "IfcSlab"]

    point_clouds = {}
    total_points = 0

    for element_type in element_types:
        elements = model.by_type(element_type)

        for element in elements:
            try:
                vertices, faces = geometry.extract_mesh_from_shape(element)

                # Sample points on mesh surface
                points = sample_points_on_mesh(vertices, faces, points_per_m2)

                point_clouds[element.GlobalId] = {
                    'points': points,
                    'element_type': element_type,
                    'name': element.Name or "Unnamed"
                }

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

    if logger:
        logger.logText("SENSOR2GRAPH", "Point cloud generated")

    return point_clouds
