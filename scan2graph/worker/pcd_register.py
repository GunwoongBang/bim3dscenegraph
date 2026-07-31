"""
Register the IFC-derived reference cloud (as-designed) to the reconstructed
sensor cloud (as-built) and report the alignment validation result.

The stage produces a source(IFC) -> target(sensor) transform and the metrics
used to validate it: inlier RMSE (residual, reported in mm), fitness
(coverage within the ICP correspondence threshold), and the ICP context
(threshold, iteration budget, convergence criteria).
"""

from pathlib import Path

import numpy as np
import open3d as o3d
import yaml

from .util import (
    load_ifc_reference_cloud,
    preprocess_point_cloud,
    global_registration,
    refine_registration,
    RegistrationValidation,
)
from .validation import log_registration_validation


# IFC-derived OBJ meshes written by export_ifc_to_sdf().
_DEFAULT_MESH_DIR = (
    Path(__file__).parent.parent
    / "ifc2pointcloud" / "src" / "robot_gazebo" / "worlds" / "ifc_world_meshes"
)

# Coarse-to-fine ICP correspondence thresholds (m).
_ICP_SCALES = [0.5, 0.2, 0.1, 0.05, 0.02, 0.01, 0.005, 0.002, 0.001]


def register_point_clouds(
    pcd_path: Path,
    csv_path: Path = None,
    ifc_model=None,
    logger=None,
    *,
    mesh_dir: Path = None,
    voxel_size: float = 0.2,
    validation_threshold: float = 0.02,
    max_iteration: int = 2000,
    relative_fitness: float = 1e-7,
    relative_rmse: float = 1e-7,
) -> tuple[Path, RegistrationValidation]:
    """
    Align the IFC reference cloud to the sensor cloud and validate the fit.

    Args:
        pcd_path: Reconstructed sensor point cloud (registration target).
        logger: Optional logger for output messages.
        csv_path: Label CSV aligned row-for-row with pcd_path. When given with
            ifc_model, the stage-3 validation (incl. the independent
            point-to-wall-plane residual) is logged once registration is done.
        ifc_model: Open ifcopenshell model, for the wall-residual metric.
        mesh_dir: Directory of IFC-derived OBJ meshes (registration source).
            Defaults to the SDF export mesh directory.
        voxel_size: Downsampling / global-registration voxel size (m).
        validation_threshold: Correspondence threshold (m) the reported
            fitness/RMSE are measured at (the "small spatial tolerance").
        max_iteration: Max ICP iterations per refinement scale.
        relative_fitness: ICP convergence criterion on the fitness delta.
        relative_rmse: ICP convergence criterion on the RMSE delta.

    Returns:
        transform_path: YAML file with the transform and validation metrics.
        validation: RegistrationValidation with fitness / inlier RMSE / threshold.
    """
    mesh_dir = Path(mesh_dir) if mesh_dir else _DEFAULT_MESH_DIR

    source = load_ifc_reference_cloud(mesh_dir)
    target = o3d.io.read_point_cloud(str(pcd_path))
    if target.is_empty():
        raise ValueError(
            f"Sensor point cloud is empty or unreadable: {pcd_path}")

    source_down, source_fpfh = preprocess_point_cloud(source, voxel_size)
    target_down, target_fpfh = preprocess_point_cloud(target, voxel_size)

    global_result = global_registration(
        source_down, target_down, source_fpfh, target_fpfh, voxel_size)

    transformation, stages = refine_registration(
        source, target, global_result.transformation,
        _ICP_SCALES, max_iteration, relative_fitness, relative_rmse)

    # Report fitness / RMSE at an explicit, meaningful tolerance so the
    # residual has context independent of the finest refinement scale.
    evaluation = o3d.pipelines.registration.evaluate_registration(
        source, target, validation_threshold, transformation)

    validation = RegistrationValidation(
        transformation=np.asarray(transformation),
        voxel_size=voxel_size,
        validation_threshold=validation_threshold,
        fitness=evaluation.fitness,
        inlier_rmse=evaluation.inlier_rmse,
        max_iteration=max_iteration,
        relative_fitness=relative_fitness,
        relative_rmse=relative_rmse,
        stages=stages,
    )

    transform_path = pcd_path.with_name(f"{pcd_path.stem}_transform.yaml")
    with open(transform_path, "w") as f:
        yaml.dump(
            {
                "matrix": validation.transformation.tolist(),
                "voxel_size": voxel_size,
                "validation_threshold_m": validation_threshold,
                "fitness": float(validation.fitness),
                "inlier_rmse_m": float(validation.inlier_rmse),
                "inlier_rmse_mm": float(validation.inlier_rmse_mm),
                "max_iteration": max_iteration,
                "relative_fitness": relative_fitness,
                "relative_rmse": relative_rmse,
            },
            f,
            default_flow_style=False,
        )

    if logger:
        logger.logText(
            "SCAN2GRAPH", f"Registration transform saved: {transform_path}")

    # Report the stage-3 metrics as soon as registration is done, so all
    # pipeline validations land in the log together.
    if csv_path is not None and ifc_model is not None:
        log_registration_validation(
            validation, pcd_path, csv_path, ifc_model, logger)

    return transform_path, validation
