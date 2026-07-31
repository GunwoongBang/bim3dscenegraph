# sensor2graph

## Overview

SENSOR2GRAPH merges sensor-derived point cloud data with a BIM graph in Neo4j.

It takes a PCD file and an ARC IFC model, optionally generates the point cloud via a ROS2/Gazebo simulation, segments and labels the point cloud against IFC geometry, registers it to the IFC reference cloud, and queries the existing BIM graph to retrieve semantic wall attributes for any picked sensor point.

Current implementation is orchestrated in `sensor2graph/graph_builder.py` and uses:
- workers in `sensor2graph/worker/*`
- point cloud/geometry helpers in `sensor2graph/worker/util/*`
- ROS2 pipeline control in `sensor2graph/worker/commander/commander.py`
- query loader in `query_manager/` (shared `QueryManager`)
- persistence layer in `sensor2graph/persistence/neo4j_ops.py`
- Cypher definitions in `query_manager/query_handler.cypher`

---

## Module Structure

```
sensor2graph/
├── __init__.py                     # Package exports: sensor2graph, QueryManager, Neo4jOperations
├── graph_builder.py                # Orchestrator: sensor2graph() - generate, process, register, query
├── worker/                         # Processing layer (IFC/PCD -> labeled point cloud)
│   ├── __init__.py                 # Re-exports all worker functions
│   ├── sdf_exporter.py             # IfcWall/IfcSlab -> OBJ meshes + Gazebo SDF world
│   ├── pcd_cleaner.py              # Floor removal by Z-cutoff -> {stem}_cleaned.pcd
│   ├── pcd_filter.py               # RANSAC plane segmentation, IfcWall labeling, unlabeled exclusion
│   ├── pcd_register.py             # Coarse-to-fine ICP of IFC reference cloud onto sensor cloud
│   ├── point_picker.py             # Interactive point pick -> ifc_global_id lookup from CSV
│   ├── validation.py               # Per-stage quality metrics logged under the "VALIDATION" phase
│   ├── commander/                  # ROS2/Gazebo pipeline control
│   │   ├── __init__.py             # Exports launch_ros2_pipeline, stop_ros2_pipeline
│   │   ├── commander.py            # Build/launch/teardown of the ifc2pointcloud workspace
│   │   └── util/                   # Shell scripts driving the ROS2 pipeline
│   │       ├── build.sh            # colcon build of the ifc2pointcloud workspace
│   │       ├── run_sim.sh          # Launch Gazebo with the generated ifc_world.sdf
│   │       ├── run_lio_sam.sh      # Launch LIO-SAM SLAM
│   │       └── run_teleop.sh       # Teleop terminal for manual robot driving
│   └── util/                       # Stateless helpers shared by the workers
│       ├── __init__.py             # Re-exports all helper functions
│       ├── geometry.py             # ifcopenshell mesh extraction (vertices/faces)
│       ├── pcd_util.py             # Open3D IO, floor removal, RANSAC planes, viewers, ICP + metrics
│       └── sdf_util.py             # OBJ writing, XML pretty-printing, name sanitizing
├── ifc2pointcloud/                 # ROS2 workspace (submodule): Gazebo world, Velodyne sim, LIO-SAM
└── persistence/                    # Persistence layer (Neo4j reads)
    ├── __init__.py                 # Exports Neo4jOperations
    └── neo4j_ops.py                # Neo4jOperations: reset_database, retrieve_wall_attr
```

---

## Inputs

- `pcd_path` (required): Path to the input PCD file
- `arc_path` (required): ARC IFC model (for geometry and wall semantics)

Entrypoint call:
- `sensor2graph(driver, pcd_path, arc_path, logger=None)`

---

## End-to-End Pipeline

### 1) Initialize

In `graph_builder.py`:
- Create `QueryManager()`
- Create `Neo4jOperations(query_manager, logger)`
- Open IFC model with `ifcopenshell.open(...)`
- Prompt user: skip or run full point cloud preparation

### 2) Generate Point Cloud (optional, if `pcd_prep=True`)

#### IFC → SDF export (`worker/sdf_exporter.py`)
- Traverse `IfcWall` and `IfcSlab` elements
- Extract mesh geometry via `ifcopenshell.geom`
- Write per-element `.obj` mesh files into `ifc2pointcloud/src/robot_gazebo/worlds/ifc_world_meshes/`
- Assemble a Gazebo SDF world file at `ifc2pointcloud/src/robot_gazebo/worlds/ifc_world.sdf`

#### ROS2 pipeline (`worker/commander/commander.py`)
- Build the `ifc2pointcloud` ROS2 workspace
- Launch Gazebo simulation (`run_sim.sh`)
- Launch LIO-SAM SLAM (`run_lio_sam.sh`)
- Open teleop terminal for manual robot driving (`run_teleop.sh`)
- On user confirmation: save the LIO-SAM map and terminate all ROS2/Gazebo processes

### 3) Post-process Point Cloud

#### Clean (`worker/pcd_cleaner.py`)
- Floor removal by Z-axis cutoff (`floor_z_cutoff = -0.555`)
- Output: `{stem}_cleaned.pcd`

#### Segment (`worker/pcd_filter.py` — `segment_point_cloud`)
- RANSAC plane detection on cleaned PCD
  - Parameters: `distance_threshold=0.02`, `min_inliers=500`, `max_planes=10`, `num_iterations=1000`
- Interactive viewer: user picks a seed point → whole plane selected
- User assigns detected plane to an `IfcWall` by index
- Output: CSV with columns `plane_label`, `ifc_type`, `ifc_global_id`, `ifc_name`

#### Exclude unlabeled planes (`worker/pcd_filter.py` — `exclude_planes`)
- Filter CSV rows where `plane_label == "unlabeled"`
- Compact PCD to retain only labeled points
- Output: `{stem}_excluded.pcd` + `{stem}_excluded.csv`

### 4) Register to IFC Geometry

In `worker/pcd_register.py` and `worker/util/pcd_util.py`:
- Source: IFC-derived reference cloud sampled from the exported OBJ meshes
- Target: the labeled sensor point cloud
- FPFH-based global registration (`voxel_size=0.2` m), then coarse-to-fine ICP over scales `0.5 … 0.001` m
- Fitness / inlier RMSE evaluated at an explicit tolerance (`validation_threshold=0.02` m)
- Output: `{stem}_transform.yaml` with the 4×4 transform and the validation metrics

### 5) Validate Stages

In `worker/validation.py` (all output routed through the `VALIDATION` logger phase):
- `[0]` Cleaning — incoming vs. surviving points after floor removal
- `[1]` Segmentation — planar cluster count and per-plane planarity RMS
- `[2]` Labeling — cluster → `IfcWall` mapping, wall coverage, clutter rejected
- `[3]` Registration — ICP fitness/RMSE plus an independent point-to-wall-plane residual

### 6) Query BIM Graph

#### Point picking (`worker/point_picker.py`)
- Open3D interactive viewer with per-wall-ID coloring
- User picks a single point → retrieve its `ifc_global_id` from the CSV

#### Neo4j lookup (`persistence/neo4j_ops.py`)
- Query `RETRIEVE_WALL_ATTRIBUTES` with the picked `ifc_global_id`
- Return wall attributes: `id`, `ifcClass`, `layerCount`

---

## Data/Query Layer

Cypher queries are stored in:
- `query_manager/query_handler.cypher`

Loaded dynamically by:
- `query_manager/` (shared `QueryManager`)

Executed by:
- `sensor2graph/persistence/neo4j_ops.py`
