# Evaluation Plan

A structured plan for evaluating the full BIM-to-robot pipeline. The pipeline is a chain of
transformations (IFC → graph → point cloud → labeled cloud → robot task → motion), so the
plan evaluates each stage in isolation **and** end-to-end, then treats robustness,
generalization, and performance as cross-cutting concerns.

## Guiding principles

- **Digital ground truth.** The pipeline is simulation-based, so the IFC model and the exact
  Gazebo poses/geometry serve as ground truth at every stage. Exploit this for quantitative,
  reproducible measurement.
- **Component vs. end-to-end.** Each stage is measured twice: once with clean ground-truth
  input (isolates the stage's own error) and once in the full pipeline (shows propagated
  error). The gap between the two is itself a result.
- **Error propagation.** Because stages are chained, upstream error compounds. Always report
  where an end-to-end failure originated.

---

## Stage 1 — bim2graph (IFC → Neo4j semantic graph)

- **RQ1.** Does the extracted graph faithfully and completely represent the IFC model's
  entities and topology?
- **Metric.**
  - Node completeness: extracted node count vs. IFC entity count, per type
    (Space, Wall, Layer, Opening, MEPElement, MEPSystem).
  - Edge correctness: precision & recall of each relationship type
    (HAS_LAYER, VOIDED_BY, BOUNDED_BY, CONTAINS, HOSTS, PENETRATED_BY).
- **Dataset.** The input IFC files (ARC/STR/MEP) as ground truth; cross-checked in an IFC
  viewer for a manually-verified subset.
- **Procedure.** Run `bim2graph`, query Neo4j for counts and relationships, compare against
  the IFC parsed independently with `ifcopenshell`. Report a confusion matrix per edge type;
  inspect false positives/negatives.

---

## Stage 2 — sdf_exporter + simulation + SLAM (IFC → point cloud)

- **RQ2.** How geometrically faithful is the generated point cloud to the source IFC, and how
  much does SLAM drift degrade it?
- **Metric.**
  - Cloud-to-mesh distance: point-to-surface RMSE and Hausdorff distance vs. the IFC mesh.
  - SLAM accuracy: Absolute Trajectory Error (ATE) and Relative Pose Error (RPE) against the
    ground-truth Gazebo trajectory.
  - Surface coverage: fraction of IFC wall surface area observed by the cloud.
- **Dataset.** IFC-derived mesh + exact Gazebo robot poses as ground truth.
- **Procedure.** Generate the world via `sdf_exporter`, drive the robot, run LIO-SAM. Align
  the resulting cloud to the IFC mesh; compute distances and coverage. Log ground-truth poses
  from Gazebo to compute ATE/RPE. Repeat over several trajectories.

---

## Stage 3 — pcd_filter (segmentation + labeling)

- **RQ3.** How accurately are point-cloud points segmented into planes and labeled with the
  correct IFC element?
- **Metric.**
  - Segmentation: number of detected planes vs. actual walls; over-/under-segmentation rate.
  - Labeling: per-wall IoU, and precision/recall of point→`ifc_global_id` assignment.
- **Dataset.** Per-point ground-truth element identity, derived from Gazebo (each simulated
  ray's hit surface is known).
- **Procedure.** Run cleaning + RANSAC segmentation + labeling. Compare each point's assigned
  label to its true source element. Report per-wall IoU and a labeling confusion matrix.
  Evaluate both on clean input (Stage-2 ground-truth cloud) and on the real SLAM cloud.

---

## Stage 4 — scan2graph (point pick → graph query)

- **RQ4.** Does selecting a sensor point retrieve the correct BIM element and its attributes
  from the graph?
- **Metric.** Retrieval accuracy: fraction of picked points whose returned wall id /
  attributes match the true element. Failure breakdown (mislabeled point vs. missing node).
- **Dataset.** Known point→element mapping + the Neo4j graph from Stage 1.
- **Procedure.** Sample picks across all labeled walls; query `RETRIEVE_WALL_ATTRIBUTES`;
  compare returned id/attributes to ground truth.

---

## Stage 5 — graph2robot (task planning + execution)

- **RQ5.** Does the robot drill the correct element at the correct location and depth, safely?
- **Metric.**
  - Target correctness: right element + right layer (semantic).
  - Positional accuracy: drill-tip error vs. intended target (mm).
  - Execution success rate: fraction of tasks MoveIt plans and executes without collision.
  - Safety: behind-wall / depth-conflict detection rate (true vs. false alarms).
- **Dataset.** Intended drill targets derived from the BIM; ground-truth geometry in Gazebo.
- **Procedure.** For a set of selected elements, run `robot_task` → `robot_gazebo`/MoveIt.
  Record planned vs. achieved drill-tip pose, plan success, and conflict-detection outcomes.

---

## End-to-end evaluation

- **RQ6.** Given an element selected in the BIM, does the system drive the robot to drill the
  correct physical location, to the correct depth, without conflict?
- **Metric.** End-to-end positional error (mm), semantic correctness (right element + layer),
  and overall task success rate — with each failure attributed to the originating stage.
- **Procedure.** Run the entire pipeline per selected element with propagated (noisy) inputs.
  Compare the final drilled pose to the BIM-intended target. Build a failure-attribution table
  mapping end-to-end failures back to Stages 1–5.

---

## Cross-cutting concerns

- **Generalization.** Repeat the full evaluation on multiple IFC models varying in building
  type, size, and wall/MEP complexity. (Single-model results show feasibility; multi-model
  results show generality — invest here.)
- **Robustness.** Sweep point-cloud noise, scan coverage, and SLAM degradation; plot accuracy
  vs. perturbation level to find breaking points.
- **Ablations.** Quantify the contribution of optional components, e.g. STR enrichment on
  layer accuracy (Stage 1), and IMU fusion (LIO vs. LiDAR-only) on cloud fidelity (Stage 2).
- **Performance.** Per-stage runtime and scaling vs. model size: graph build time, simulation
  duration, query latency, planning time.

---

## Threats to validity

- **Simulated sensing.** The point cloud is simulated, not from a real LiDAR — this is what
  makes the ground truth clean, but it caps external validity. Mitigate by adding at least one
  real-scan case or a realistic sensor-noise model, and report the sim-to-real gap explicitly.
- **Limited model diversity.** Conclusions are bounded by the IFC models tested; state the
  range covered.
- **Interactive steps.** Manual point picking / teleop introduce operator variance; where
  relevant, report across multiple operators or automate for repeatability.
