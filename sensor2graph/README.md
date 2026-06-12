# SENSOR2GRAPH

## Overview

SENSOR2GRAPH merges sensor-derived point cloud data with a BIM graph in Neo4j.

It takes a PCD file and an ARC IFC model, optionally generates the point cloud via a ROS2/Gazebo simulation, segments and labels the point cloud against IFC geometry, and queries the existing BIM graph to retrieve semantic wall attributes for any picked sensor point.

Current implementation is orchestrated in `sensor2graph/graph_builder.py` and uses:
- workers in `sensor2graph/worker/*`
- ROS2 pipeline control in `sensor2graph/worker/commander/commander.py`
- persistence layer in `sensor2graph/persistence/neo4j_ops.py`
- Cypher definitions in `query_manager/query_handler.cypher`

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
- Write per-element `.obj` mesh files
- Assemble a Gazebo SDF world file at `ifc2pointcloud/src/robot_gazebo/worlds/ifc_world.sdf`

#### ROS2 pipeline (`worker/commander/commander.py`)
- Build the `ifc2pointcloud` ROS2 workspace
- Launch Gazebo simulation (`run_sim.sh`)
- Launch LIO-SAM SLAM (`run_lio_sam.sh`)
- Open teleop terminal for manual robot driving (`run_teleop.sh`)
- On user confirmation: save the LIO-SAM map and terminate all ROS2/Gazebo processes

### 3) Post-process Point Cloud

#### Clean (`worker/pcd_cleaner.py`)
- Floor removal by Z-axis cutoff
- Output: `{stem}_cleaned.pcd`

#### Segment (`worker/pcd_filter.py` — `segment_point_cloud`)
- RANSAC plane detection on cleaned PCD
  - Parameters: `distance_threshold=0.02`, `min_inliers=500`, `max_planes=10`
- Interactive viewer: user picks a seed point → whole plane selected
- User assigns detected plane to an `IfcWall` by index
- Output: CSV with columns `plane_label`, `ifc_type`, `ifc_global_id`, `ifc_name`

#### Exclude unlabeled planes (`worker/pcd_filter.py` — `exclude_planes`)
- Filter CSV rows where `plane_label == "unlabeled"`
- Compact PCD to retain only labeled points
- Output: `{stem}_excluded.pcd` + `{stem}_excluded.csv`

### 4) Query BIM Graph

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

---

## How to Run

From project root:
- Ensure Neo4j is running and `.env` has credentials (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- Ensure ROS2 Humble and Gazebo are installed (required only for point cloud generation)
- Set PCD and IFC paths in `main.py`
- Run `main.py`
