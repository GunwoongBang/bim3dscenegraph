"""
Point picking and "ifc_global_id" retrieval from point cloud.
"""

from pathlib import Path

import numpy as np
import open3d as o3d
import pandas as pd


def retrieve_picked_point_id(pcd_path: Path, csv_path: Path, logger=None) -> str:
    if logger:
        logger.logText("SENSOR2GRAPH", "Launching point picker visualizer...")

    cloud = o3d.io.read_point_cloud(str(pcd_path))
    points = np.asarray(cloud.points)
    labels = pd.read_csv(csv_path)

    if len(points) != len(labels):
        raise ValueError(
            f"PCD point count ({len(points)}) does not match CSV row count ({len(labels)})."
        )

    ids = []

    for id in labels["ifc_global_id"]:
        if id in ids:
            continue
        ids.append(id)

    # Assign random colors to each unique ID
    colors = np.random.rand(len(ids), 3) * 0.7 + 0.2
    color_dict = dict(zip(ids, colors))
    point_colors = np.array([color_dict[id] for id in labels["ifc_global_id"]])

    # Create a colored point cloud for point picking
    picker_cloud = o3d.geometry.PointCloud()
    picker_cloud.points = cloud.points
    picker_cloud.colors = o3d.utility.Vector3dVector(point_colors)

    visualizer = o3d.visualization.VisualizerWithEditing()
    visualizer.create_window(window_name="Plane Picker")
    visualizer.add_geometry(picker_cloud)
    visualizer.run()
    picked_index = visualizer.get_picked_points()
    visualizer.destroy_window()

    if not picked_index:
        if logger:
            logger.logText("SENSOR2GRAPH", "No point was picked.")

    picked_global_id = labels.iloc[picked_index[0]]["ifc_global_id"]

    if logger:
        logger.logText(
            "SENSOR2GRAPH", "Sensor graph is connected to BIM graph")

    return picked_global_id
