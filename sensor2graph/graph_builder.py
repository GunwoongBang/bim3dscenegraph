"""
Main orchestrator for SENSOR2GRAPH.

This module coordinates the conversion of BIM model geometry into
a point cloud representation and persistence to Neo4j graph database.
"""

import os

import ifcopenshell
import open3d as o3d

from .extractor import (
    generate_point_cloud,
    visualize_point_cloud,
    export_point_cloud,
    reconstruct_poisson_from_laz,
    PoissonConfig
)


def sensor2graph(pcd_path, logger=None):
    """
    Generates a sensor-derived graph from an IFC model and persists to Neo4j.

    This function orchestrates the full pipeline:
        1. Load IFC model
        2. Extract point cloud from point cloud IFC model
        3. Reconstruct surface mesh from point cloud

    Args:
        pcd_path: Path to the PCD IFC file
        logger: Optional logger for output messages
    """
    if logger:
        logger.logText("SENSOR2GRAPH", "PCD IFC model loaded")

    # Load IFC model
    model = ifcopenshell.open(pcd_path)

    # =========================================================================
    # Generate point cloud from IFC
    # =========================================================================
    point_cloud = generate_point_cloud(model, logger)

    # Visualize & export the point cloud
    visualize_point_cloud(point_cloud)
    export_point_cloud(pcd_path, point_cloud, logger)

    # =========================================================================
    # Reconstruct surface mesh from point cloud
    # =========================================================================
    model_name = os.path.splitext(os.path.basename(pcd_path))[0]

    laz_path = f"pc_models/{model_name}.laz"
    mesh_path = f"pc_models/{model_name}_poisson.ply"

    stats = reconstruct_poisson_from_laz(
        laz_path, mesh_path, PoissonConfig(poisson_depth=10), logger)

    if logger:
        logger.logText(
            "SENSOR2GRAPH",
            "Poisson mesh ready: "
            f"vertices={stats['mesh_vertices']} triangles={stats['mesh_triangles']}",
        )

    mesh = o3d.io.read_triangle_mesh(mesh_path)
    if mesh.is_empty():
        if logger:
            logger.logText(
                "SENSOR2GRAPH", f"Cannot visualize empty mesh: {mesh_path}")
    else:
        mesh.compute_vertex_normals()
        coord_frame = o3d.geometry.TriangleMesh.create_coordinate_frame(
            size=1.0)
        o3d.visualization.draw_geometries(
            [mesh, coord_frame],
            window_name="Poisson Reconstruction",
            width=1200,
            height=800,
        )

    # =========================================================================
    # Extract data from point cloud
    # =========================================================================

    if logger:
        logger.logText("SENSOR2GRAPH", "SENSOR2GRAPH under construction")
