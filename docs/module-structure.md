# Module Structure

Each repository's package organization, annotated with the role of every module.

`bimscanfusion` is a Python orchestration layer; both of its pipelines follow the same
pattern — an **orchestrator** (`graph_builder.py`) that fans out to stateless **workers**,
writing through a **persistence** layer, over a **shared query layer** (`query_manager/`).
`ifc2pointcloud` and `graph2robot` are ROS 2 workspaces, each a set of cooperating packages.

---

## bimscanfusion — Python orchestration + graph

```text
bimscanfusion/
├── main.py                             # entrypoint: open Neo4j driver, run both pipelines
├── logger.py                           # shared file logger
│
├── bim2graph/                          # pipeline 1 — IFC → Neo4j semantic graph
│   ├── graph_builder.py                # orchestrator: extract entities → persist
│   ├── worker/                         # stateless IFC extractors
│   │   ├── space_extractor.py          # IfcSpace nodes
│   │   ├── wall_extractor.py           # IfcWall nodes + material layers (+ STR enrichment)
│   │   ├── opening_extractor.py        # IfcOpeningElement nodes + VOIDED_BY edges
│   │   ├── relationship_extractor.py   # space–wall boundaries (BOUNDED_BY)
│   │   ├── mep_extractor.py            # MEP systems/elements + memberships & host edges
│   │   └── util/                       # geometry + per-domain helpers
│   └── persistence/
│       └── neo4j_ops.py                # Neo4j writer: schema, node upserts, edge creation
│
├── scan2graph/                         # pipeline 2 — point cloud → label → graph query
│   ├── graph_builder.py                # orchestrator: generate → clean → segment → query
│   ├── worker/
│   │   ├── sdf_exporter.py             # IFC geometry → Gazebo SDF world + OBJ meshes
│   │   ├── pcd_cleaner.py              # floor removal (Z cutoff)
│   │   ├── pcd_filter.py               # RANSAC segmentation, labeling, plane exclusion
│   │   ├── point_picker.py             # interactive pick → ifc_global_id
│   │   ├── commander/                  # ROS 2 / Gazebo pipeline control
│   │   │   └── commander.py            # build, launch sim + LIO-SAM, teleop, save, stop
│   │   └── util/                       # geometry + PCD/SDF helpers
│   ├── persistence/
│   │   └── neo4j_ops.py                # Neo4j reader: wall-attribute lookup by id
│   └── ifc2pointcloud/                 # git submodule — ROS 2 workspace (see below)
│
├── query_manager/                      # shared Cypher loader (used by both pipelines)
│   ├── query_manager.py                # parses named queries, hands them to persistence
│   └── query_handler.cypher            # all node/edge/lookup Cypher definitions
│
├── ifc_models/                         # input IFC files (ARC / STR / MEP)
└── pc_models/                          # input / output PCD files
```

---

## ifc2pointcloud — ROS 2 workspace (git submodule of scan2graph)

Generates a point cloud by driving a simulated robot through the IFC-derived world.

```text
ifc2pointcloud/
└── src/
    ├── robot_gazebo/                   # Gazebo simulation: worlds, models, launch
    │   ├── worlds/                     # ifc_world.sdf + generated meshes
    │   ├── models/                     # robot + sensor models
    │   ├── urdf/
    │   └── launch/                     # robot_sim.launch.py (sim entry point)
    ├── robot_description/              # robot URDF / xacro, frame definitions
    ├── robot_control/                  # teleop control
    │   └── scripts/                    # robot_control.py → publishes /cmd_vel
    ├── velodyne_simulator/             # simulated Velodyne LiDAR
    │   ├── velodyne_description/       # sensor URDF
    │   ├── velodyne_gazebo_plugins/    # PointCloud2-publishing Gazebo plugin
    │   └── velodyne_simulator/         # top-level sim package
    └── LIO-SAM-ros2/                   # LiDAR-inertial odometry + mapping (SLAM backend)
```

---

## graph2robot — ROS 2 workspace

Turns the Neo4j BIM graph into executable robot drilling tasks (Husky + UR5e).

```text
graph2robot/
└── src/
    ├── robot_graph/                # exposes Neo4j BIM entities as ROS 2 services
    │   └── graph_server            # query graph → serve BIM entities
    ├── robot_task/                 # BIM data → task plan
    │   ├── task_manager            # fetch BIM via services, fan out /ifc/* + /matrix
    │   ├── drill_context_builder   # build drill context (wall, facing, layers)
    │   ├── drill_executor          # compute robot base pose + drill-tip target points
    │   └── drilling_task.launch.py
    ├── robot_rviz/                 # visualization + interactive element selection
    │   ├── pointcloud_publisher    # publish the point-cloud scan once on /cloud
    │   ├── task_distributor        # place clickable markers, emit /task/selected_element
    │   ├── task_representer        # compute working-zone hazard map (RViz + MoveIt)
    │   └── robot_rviz.launch.py
    └── robot_gazebo/               # simulation + MoveIt trajectory execution
        ├── world_spawner           # spawn IFC geometry into the Gazebo world
        ├── robot_spawner           # spawn + teleport Husky+UR5e to target pose
        ├── robot_motion_planner    # MoveIt plan/execute; stop on behind-wall depth conflict
        └── robot_gazebo.launch.py
```
