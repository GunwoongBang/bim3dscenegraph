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
                color = extract_ifc_color(materials)
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
