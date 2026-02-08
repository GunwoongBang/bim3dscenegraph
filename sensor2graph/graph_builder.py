"""
Main orchestrator for Sensor-to-Graph conversion.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import numpy as np
import open3d as o3d
import ifcopenshell

from .query_manager import QueryManager
from .persistence import Neo4jOperations
from .extractor import (
    generate_point_cloud,
)


def visualize_point_cloud(point_clouds, color_by_element=True):
    """
    Visualize point clouds using Open3D.

    Args:
        point_clouds: dict from generate_point_cloud()
                      {global_id: {'points': np.array, 'element_type': str}}
        color_by_element: if True, each element gets a different color
    """
    # Color palette for different elements
    colors_palette = [
        [0.8, 0.2, 0.2],  # Red
        [0.2, 0.8, 0.2],  # Green
        [0.2, 0.2, 0.8],  # Blue
        [0.8, 0.8, 0.2],  # Yellow
        [0.8, 0.2, 0.8],  # Magenta
        [0.2, 0.8, 0.8],  # Cyan
        [0.9, 0.5, 0.2],  # Orange
        [0.5, 0.2, 0.9],  # Purple
    ]

    # Combine all points
    all_points = []
    all_colors = []

    for i, (global_id, data) in enumerate(point_clouds.items()):
        points = data['points']
        if len(points) == 0:
            continue

        all_points.append(points)

        if color_by_element:
            color = colors_palette[i % len(colors_palette)]
            all_colors.append(np.tile(color, (len(points), 1)))
        else:
            # Color by element type
            if data['element_type'] == 'IfcWall':
                color = [0.7, 0.7, 0.7]  # Gray for walls
            elif data['element_type'] == 'IfcSlab':
                color = [0.5, 0.3, 0.1]  # Brown for slabs
            else:
                color = [0.5, 0.5, 0.5]  # Default gray
            all_colors.append(np.tile(color, (len(points), 1)))

    if not all_points:
        print("No points to visualize")
        return

    # Create Open3D point cloud
    combined_points = np.vstack(all_points)
    combined_colors = np.vstack(all_colors)

    pcd = o3d.geometry.PointCloud()
    pcd.points = o3d.utility.Vector3dVector(combined_points)
    pcd.colors = o3d.utility.Vector3dVector(combined_colors)

    # Add coordinate frame for reference
    coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(size=1.0)

    # Visualize
    print(
        f"Visualizing {len(combined_points)} points from {len(point_clouds)} elements")
    print("Controls: Left-click + drag to rotate, Scroll to zoom, Middle-click + drag to pan")
    o3d.visualization.draw_geometries(
        [pcd, coord_frame],
        window_name="Point Cloud from IFC",
        width=1200,
        height=800,
        point_show_normal=False
    )


def sensor2graph(driver, pcd_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

     This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract geometry (point cloud) from architectural elements
        3. 

    Args:
        driver: Neo4j driver instance
        pcd_path: Path to the PCD IFC file
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText(
            "SENSOR2GRAPH", "Starting point cloud generation from IFC")

    # Initialize components
    query_manager = QueryManager()
    neo4j_ops = Neo4jOperations(query_manager, logger)

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    # =========================================================================
    # Generate point cloud from IFC
    # =========================================================================
    point_clouds = generate_point_cloud(
        model,
        element_types=["IfcWall", "IfcSlab"],
        points_per_m2=100,  # Adjust density as needed
        logger=logger
    )

    # Visualize the point cloud
    visualize_point_cloud(point_clouds, color_by_element=True)

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
