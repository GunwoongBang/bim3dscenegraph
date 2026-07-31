# Data Representation Across the Pipeline

How the building data changes form at each stage — from the source IFC model, through
the Neo4j semantic graph, into a 3D point cloud, and finally into executable robot motion.
Each node shows the **data format** and its role; edge labels name the transform
(and the module that performs it).

```mermaid
flowchart TB
    IFC["<b>IFC (STEP / .ifc)</b><br/>ARC · STR · MEP"]

    GRAPH["<b>Neo4j property graph</b><br/>nodes + relationships"]

    SDF["<b>SDF world + OBJ meshes</b><br/>tessellated geometry"]

    PCD["<b>Point cloud (.pcd)</b><br/>raw XYZ points"]

    LPCD["<b>Labeled point cloud</b><br/>.pcd + .csv"]

    JSON["<b>BIM entities (JSON)</b><br/>ROS service payload"]

    TASK["<b>Drill task parameters</b><br/>per-element plan"]

    TRAJ["<b>Robot trajectory</b><br/>MoveIt joint path"]

    IFC -->|"extract entities + topology<br/>(bim2graph)"| GRAPH
    IFC -->|"tessellate geometry<br/>(sdf_exporter)"| SDF
    SDF -->|"LiDAR sim + LIO-SAM SLAM"| PCD
    PCD -->|"clean → RANSAC segment → label<br/>(scan2graph)"| LPCD
    LPCD -.->|"pick point → ifc_global_id<br/>confirms BIM–sensor match"| GRAPH

    GRAPH -->|"query → serialize<br/>(robot_graph)"| JSON
    JSON -->|"compute drill targets<br/>(robot_task)"| TASK
    TASK -->|"plan + execute<br/>(robot_gazebo / MoveIt)"| TRAJ
```

## Summary of representations

| # | Representation | Format | Produced by |
|---|---|---|---|
| 1 | Source BIM | `IFC` (STEP) | — (input) |
| 2 | Semantic graph | Neo4j property graph | `bim2graph` |
| 3 | Simulation world | `SDF` + `OBJ` | `sdf_exporter` |
| 4 | Raw point cloud | `PCD` (XYZ) | LiDAR sim + LIO-SAM |
| 5 | Labeled point cloud | `PCD` + `CSV` | `scan2graph` |
| 6 | Robot-facing BIM | `JSON` | `robot_graph` |
| 7 | Task plan | drill parameters | `robot_task` |
| 8 | Motion | MoveIt trajectory | `robot_gazebo` |
