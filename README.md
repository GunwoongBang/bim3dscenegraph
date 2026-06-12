# BIM 3D Scene Graph

## Overview

BIM 3D Scene Graph constructs a semantically rich 3D scene graph by fusing BIM data and sensor-derived point clouds into a Neo4j graph database.

The project is composed of two main pipelines:

| Module | Purpose |
|---|---|
| `bim2graph` | Parse IFC models (ARC/STR/MEP) and persist a semantic graph to Neo4j |
| `sensor2graph` | Generate or load a point cloud, label it against IFC geometry, and query the BIM graph from a picked sensor point |

Both pipelines are orchestrated from `main.py` and share a common `QueryManager` and `Neo4jOperations` layer.

---

## Repository Structure

```
bim3dscenegraph/
├── main.py                     # Top-level entrypoint
├── logger.py                   # Shared file logger
├── bim2graph/                  # BIM → Neo4j graph pipeline
│   ├── graph_builder.py
│   ├── extractor/              # Spaces, walls, layers, openings, MEP
│   ├── persistence/
│   └── README.md
├── sensor2graph/               # Sensor → point cloud → BIM graph query
│   ├── graph_builder.py
│   ├── worker/                 # SDF export, PCD cleaning, segmentation, picking
│   │   └── commander/          # ROS2/Gazebo pipeline control
│   ├── persistence/
│   └── README.md
├── query_manager/              # Shared Cypher query loader
│   ├── query_manager.py
│   └── query_handler.cypher
├── ifc_models/                 # Input IFC files (ARC, STR, MEP)
└── pc_models/                  # Input/output PCD files
```

---

## Full Pipeline

```
IFC Models (ARC / STR / MEP)
        │
        ▼
  ┌─────────────┐
  │  BIM2GRAPH  │  ← bim2graph/
  └─────────────┘
        │  Nodes: Space, Wall, Layer, Opening, MEPElement, MEPSystem
        │  Edges: HAS_LAYER, VOIDED_BY, BOUNDED_BY, PASSES_THROUGH, VISIBLE_IN
        ▼
   Neo4j Graph
        ▲
        │  RETRIEVE_WALL_ATTRIBUTES (by ifc_global_id)
  ┌──────────────────┐
  │  SENSOR2GRAPH    │  ← sensor2graph/
  └──────────────────┘
        ▲
        │  Segmented, labeled PCD (ifc_global_id per point)
  ┌───────────────────────┐
  │  Point Cloud Pipeline │
  │  ┌─────────────────┐  │
  │  │ IFC → SDF world │  │  sdf_exporter.py
  │  └────────┬────────┘  │
  │           ▼           │
  │  ROS2 / Gazebo sim    │  commander.py
  │  LIO-SAM SLAM scan    │
  │           ▼           │
  │  Clean PCD            │  pcd_cleaner.py
  │  RANSAC segmentation  │  pcd_filter.py
  │  Interactive labeling │
  └───────────────────────┘
```

### Step 1 — BIM2GRAPH

Reads ARC (+ optional STR, MEP) IFC files, extracts semantic entities and topology, and persists nodes and relationships to Neo4j.

See [bim2graph/README.md](bim2graph/README.md) for the full breakdown.

### Step 2 — SENSOR2GRAPH

Takes a PCD file and the same ARC IFC model. If point cloud data is not yet available, it generates one via a Gazebo simulation using the IFC geometry, then runs LIO-SAM SLAM. The resulting cloud is cleaned, segmented by RANSAC plane detection, and interactively labeled against IFC walls. Finally, the user picks a sensor point and its `ifc_global_id` is used to query the BIM graph in Neo4j.

See [sensor2graph/README.md](sensor2graph/README.md) for the full breakdown.

---

## How to Run

### Prerequisites

- Python 3.10+
- Neo4j running locally (or remote)
- `ifcopenshell`, `open3d`, `numpy`, `pandas`, `python-dotenv`, `neo4j` Python packages
- ROS2 Humble + Gazebo (required only for point cloud generation step)

### Configuration

Create a `.env` file in the project root:

```
NEO4J_URI=neo4j://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password
```

Set IFC and PCD paths in `main.py`:

```python
ARC_PATH = Path("ifc_models/test/test_ARC.ifc")
STR_PATH = Path("ifc_models/test/test_STR.ifc")
MEP_PATH = Path("ifc_models/test/test_MEP.ifc")
PCD_PATH = Path("pc_models/cloudGlobal.pcd")
```

### Run

```bash
python main.py
```

The pipeline will:
1. Connect to Neo4j
2. Run BIM2GRAPH — parse IFC files and populate the graph
3. Run SENSOR2GRAPH — process the point cloud and query the graph
4. Close the Neo4j driver

Logs are written to `log/project.log`.

Neo4j browser: `http://localhost:7474/browser/`
