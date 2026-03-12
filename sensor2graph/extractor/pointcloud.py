"""
Point cloud generation from IFC model.
"""

import os
import numpy as np
import open3d as o3d
import laspy

from . import geometry


def _extract_ifc_color(materials):
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
            normal = _face_normal(vertices, face)
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


def _compute_building_bbox(model, element_types):
    """
    Compute the overall bounding box of all elements of the given types.

    Args:
        model: ifcopenshell model instance
        element_types: list of IFC class strings

    Returns:
        (bbox_min, bbox_max): numpy arrays [x,y,z] or (None, None) if no geometry
    """
    all_verts = []
    for et in element_types:
        for element in model.by_type(et):
            try:
                vertices, _ = geometry.extract_mesh_from_shape(element)
                all_verts.append(vertices)
            except Exception:
                pass
    if not all_verts:
        return None, None
    combined = np.vstack(all_verts)
    return combined.min(axis=0), combined.max(axis=0)


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

    building_bbox = None
    if indoor_only:
        bbox_min, bbox_max = _compute_building_bbox(model, element_types)
        if bbox_min is not None:
            building_bbox = (bbox_min, bbox_max)
        if logger:
            logger.logText(
                "SENSOR2GRAPH",
                f"Indoor-only mode: building bbox min={np.round(bbox_min, 2) if bbox_min is not None else None}, "
                f"max={np.round(bbox_max, 2) if bbox_max is not None else None}"
            )

    point_clouds = {}
    all_points = []
    all_colors = []
    total_points = 0

    for element_type in element_types:
        elements = model.by_type(element_type)

        for element in elements:
            try:
                vertices, faces, materials = geometry.extract_mesh_from_shape(
                    element, include_materials=True)

                # Sample points on mesh surface (exterior faces filtered if indoor_only)
                points = sample_points_on_mesh(
                    vertices, faces, points_per_m2, building_bbox)

                # Use IFC-coded material color only.
                color = _extract_ifc_color(materials)
                if color is None:
                    if logger:
                        logger.logText(
                            "SENSOR2GRAPH",
                            f"Skipped {element_type} {element.GlobalId}: no IFC style color"
                        )
                    continue
                colors = np.tile(color, (len(points), 1))

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


def visualize_point_cloud(point_cloud):
    # Visualize the point cloud with colors (commented out for now)
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
        size=1.0)

    o3d.visualization.draw_geometries(
        [point_cloud, coord_frame],
        window_name="Point Cloud from IFC",
        width=800,
        height=600
    )


def export_point_cloud(pcd_path, point_cloud, logger=None):
    model_name = os.path.splitext(os.path.basename(pcd_path))[0]
    laz_path = f"pc_models/{model_name}.laz"

    # Convert Open3D point cloud to laspy point format
    points = np.asarray(point_cloud.points)
    colors = np.asarray(point_cloud.colors)

    # Create LAZ file with points and RGB colors
    las = laspy.create()
    las.x = points[:, 0]
    las.y = points[:, 1]
    las.z = points[:, 2]

    # Scale colors from [0, 1] to [0, 65535] (16-bit)
    las.red = (colors[:, 0] * 65535).astype(np.uint16)
    las.green = (colors[:, 1] * 65535).astype(np.uint16)
    las.blue = (colors[:, 2] * 65535).astype(np.uint16)

    las.write(laz_path)

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Point cloud exported to {laz_path}")
