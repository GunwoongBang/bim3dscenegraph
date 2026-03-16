"""
Point cloud generation from IFC model.
"""

import os
import numpy as np
import open3d as o3d
import laspy

from .utils import (
    extract_ifc_color,
    sample_points_on_mesh,
    transform_point_cloud,
)
from . import geometry


def generate_point_cloud(model, element_types, points_per_m2, translation, yaw_degrees, logger=None):
    """
    Generate a point cloud from the mesh surfaces of specified IFC element types.

    Args:
        model: ifcopenshell model instance
        element_types: List of IFC element types to include in the point cloud
        points_per_m2: Sampling density (number of points per square meter)
        translation: tuple (x, y, z) - translation in meters
        yaw_degrees: float - rotation around Z-axis in degrees
        logger: Optional logger for output messages

    Returns:
        combined_pcd: Open3D point cloud with all points and colors
    """
    building_bbox = None

    # Extract mesh geometry once per element and reuse for bbox + sampling.
    extracted_elements = []
    all_vertices = []

    for element_type in element_types:
        elements = model.by_type(element_type)

        for element in elements:
            try:
                vertices, faces, materials = geometry.extract_mesh_from_shape(
                    element)
                extracted_elements.append(
                    (element_type, element, vertices, faces, materials))
                all_vertices.append(vertices)
            except Exception as e:
                if logger:
                    logger.logText(
                        "SENSOR2GRAPH", f"Failed to process {element.GlobalId}: {e}")

    if all_vertices:
        combined_vertices = np.vstack(all_vertices)
        building_bbox = (combined_vertices.min(axis=0),
                         combined_vertices.max(axis=0))

    point_clouds = {}
    all_points = []
    all_colors = []
    total_points = 0

    for element_type, element, vertices, faces, materials in extracted_elements:
        # Sample points on mesh surface (exterior faces filtered if indoor_only)
        points = sample_points_on_mesh(
            vertices, faces, points_per_m2, building_bbox)

        # Use IFC-coded material color only.
        color = extract_ifc_color(materials)
        if color is None:
            if logger:
                logger.logText(
                    "SENSOR2GRAPH", f"Skipped {element_type} {element.GlobalId}: no IFC style color")
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
                "SENSOR2GRAPH", f"Sampled {len(points)} points from {element_type} {element.GlobalId}")

    # Combine all points and colors
    if all_points:
        combined_points = np.vstack(all_points)
        combined_colors = np.vstack(all_colors)

        # Apply transformation (translation + yaw rotation)
        if translation != (0, 0, 0) or yaw_degrees != 0:
            combined_points = transform_point_cloud(
                combined_points, translation, yaw_degrees)
            if logger:
                logger.logText(
                    "SENSOR2GRAPH", f"Applied transform: translation={translation}, yaw={yaw_degrees}°")

        # Create Open3D point cloud with colors
        combined_pcd = o3d.geometry.PointCloud()
        combined_pcd.points = o3d.utility.Vector3dVector(combined_points)
        combined_pcd.colors = o3d.utility.Vector3dVector(combined_colors)
    else:
        combined_pcd = o3d.geometry.PointCloud()

    if logger:
        logger.logText(
            "SENSOR2GRAPH", f"Total: {total_points} points from {len(point_clouds)} elements")

    return combined_pcd


def visualize_point_cloud(point_cloud):
    # Visualize the point cloud with colors (commented out for now)
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0)

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
