"""
Stage validation for SCAN2GRAPH.

Reports per-stage quality metrics to the log while the pipeline runs:

  1. Segmentation - RANSAC plane clusters: count, inliers, planarity residual.
  2. Labeling     - cluster -> IfcWall assignment: coverage, clutter rejected.
  3. Registration - ICP headline metrics plus an independent point-to-wall-plane
                    residual tied to the labeled walls (does not reuse the ICP
                    correspondence set nor the RANSAC planes).

All output is routed through the "VALIDATION" logger phase so it can be grepped
out of the run log.
"""

from pathlib import Path

import numpy as np
import open3d as o3d
import pandas as pd

from .util import extract_mesh_from_shape, RegistrationValidation


def _emit(logger, lines: list) -> None:
    """Print a validation block and mirror each line into the run log."""
    print("\n" + "\n".join(lines) + "\n")
    if logger:
        for line in lines:
            logger.logText("VALIDATION", line)


def log_cleaning_validation(input_count: int, output_count: int, logger=None) -> None:
    """
    Stage 0: how much of the raw scan survived floor removal?

    Args:
        input_count: Point count of the raw cloud.
        output_count: Point count after cleaning.
        logger: Optional logger.
    """
    removed = input_count - output_count
    pct = (removed / input_count * 100.0) if input_count else 0.0
    _emit(
        logger,
        [
            "[0] Cleaning validation (floor removal):",
            f"  Incoming points : {input_count}",
            f"  Output points   : {output_count}",
            f"  Removed         : {removed} ({pct:.2f}%)",
        ],
    )


def log_segmentation_validation(plane_groups: list, walls: list, logger=None) -> None:
    """
    Stage 1: did RANSAC recover flat planar clusters?

    Args:
        plane_groups: Plane groups from extract_plane_groups (with rms_residual).
        walls: IfcWall elements in the model (for context only).
        logger: Optional logger.
    """
    lines = [
        "[1] Segmentation validation (RANSAC planes):",
        f"  Planar clusters extracted : {len(plane_groups)}",
        f"  IfcWall count in model    : {len(walls)}",
        "  Per-plane planarity (inlier RMS distance to fitted plane):",
    ]
    for pg in plane_groups:
        rms_mm = pg.get("rms_residual", float("nan")) * 1000.0
        lines.append(
            f"    plane {int(pg['plane_id']):02d} | "
            f"inliers={pg['point_count']:6d} | RMS={rms_mm:6.2f} mm"
        )
    _emit(logger, lines)


def log_labeling_validation(
    plane_groups: list, plane_semantics: dict, walls: list, logger=None
) -> None:
    """
    Stage 2: was each cluster tied to the correct wall, clutter rejected?

    Args:
        plane_groups: All plane groups extracted during segmentation.
        plane_semantics: {plane_id: {ifc_type, ifc_global_id, ifc_name}} labels.
        walls: IfcWall elements in the model.
        logger: Optional logger.
    """
    labeled_ids = {sem["ifc_global_id"] for sem in plane_semantics.values()}
    total = len(plane_groups)
    labeled = len(plane_semantics)

    lines = [
        "[2] Labeling validation (cluster -> IfcWall):",
        f"  Labeled clusters          : {labeled}/{total}",
        f"  Discarded as clutter      : {total - labeled}",
        f"  Wall coverage             : {len(labeled_ids)}/{len(walls)} walls got a plane",
        "  Cluster -> wall mapping:",
    ]
    for plane_id, sem in sorted(plane_semantics.items()):
        lines.append(
            f"    plane {int(plane_id):02d} -> {sem['ifc_global_id']} ({sem['ifc_name']})"
        )

    lines.append("  Per-wall status:")
    for wall in walls:
        gid = getattr(wall, "GlobalId", "") or ""
        name = getattr(wall, "Name", None) or "Unnamed"
        status = "labeled" if gid in labeled_ids else "unlabeled"
        lines.append(f"    {gid} ({name}): {status}")

    _emit(logger, lines)


def _wall_plane_residuals(
    points_ifc: np.ndarray, wall_verts: np.ndarray
) -> np.ndarray:
    """
    Perpendicular distances (m) of labeled points to their wall's observed face.

    The wall's surface normal is the smallest-variance PCA axis of its vertices.
    A wall has two parallel faces along that axis; the sensor observes one, so
    the residual is measured against whichever face the cluster sits nearest.

    Args:
        points_ifc: (N, 3) labeled sensor points in the IFC frame.
        wall_verts: (M, 3) IFC wall mesh vertices in the IFC frame.

    Returns:
        (N,) array of absolute perpendicular residuals in metres.
    """
    centroid = wall_verts.mean(axis=0)
    cov = np.cov((wall_verts - centroid).T)
    _, eigvecs = np.linalg.eigh(cov)
    normal = eigvecs[:, 0]  # smallest eigenvalue -> wall-thickness direction

    proj_points = (points_ifc - centroid) @ normal
    proj_verts = (wall_verts - centroid) @ normal
    faces = np.array([proj_verts.min(), proj_verts.max()])
    observed_face = faces[np.argmin(np.abs(faces - proj_points.mean()))]

    return np.abs(proj_points - observed_face)


def log_registration_validation(
    validation: RegistrationValidation,
    pcd_path: Path,
    csv_path: Path,
    ifc_model,
    logger=None,
) -> None:
    """
    Stage 3: does the aligned BIM geometry coincide with the as-built scan?

    Logs the ICP headline metrics (inlier RMSE, fitness, threshold, convergence)
    and an independent point-to-wall-plane residual computed from the labeled
    walls, which does not reuse the ICP correspondence set.

    Args:
        validation: RegistrationValidation from merge_point_clouds.
        pcd_path: Labeled (excluded) sensor point cloud.
        csv_path: Label CSV aligned row-for-row with pcd_path.
        ifc_model: Open ifcopenshell model (for wall geometry).
        logger: Optional logger.
    """
    lines = ["[3] Registration validation (ICP + independent wall residual):"]
    lines.extend("  " + line for line in validation.report().splitlines())

    # --- Independent point-to-wall-plane residual ---
    points = np.asarray(o3d.io.read_point_cloud(str(pcd_path)).points)
    labels = pd.read_csv(csv_path)

    if len(points) != len(labels):
        lines.append(
            "  Independent wall residual : skipped "
            f"(PCD points {len(points)} != CSV rows {len(labels)})"
        )
        _emit(logger, lines)
        return

    # Bring sensor points into the IFC frame (transform maps IFC -> sensor).
    transform_inv = np.linalg.inv(np.asarray(validation.transformation))
    points_h = np.c_[points, np.ones(len(points))]
    points_ifc = (transform_inv @ points_h.T).T[:, :3]

    wall_by_gid = {w.GlobalId: w for w in ifc_model.by_type("IfcWall")}
    gids = labels["ifc_global_id"].astype(str).values

    all_residuals = []
    per_wall = []
    for gid in pd.unique(gids):
        if gid in ("", "nan") or gid not in wall_by_gid:
            continue
        try:
            verts, _, _ = extract_mesh_from_shape(wall_by_gid[gid])
        except Exception:
            continue
        if verts.size == 0:
            continue

        mask = gids == gid
        residuals = _wall_plane_residuals(points_ifc[mask], verts)
        all_residuals.append(residuals)
        per_wall.append((gid, residuals))

    if not all_residuals:
        lines.append("  Independent wall residual : no labeled walls resolved")
        _emit(logger, lines)
        return

    residuals = np.concatenate(all_residuals)
    lines.append("  Independent point-to-wall-plane residual (labeled walls):")
    lines.append(
        f"    overall  | mean={residuals.mean() * 1000:6.2f} mm | "
        f"RMS={np.sqrt(np.mean(residuals ** 2)) * 1000:6.2f} mm | "
        f"max={residuals.max() * 1000:6.2f} mm | pts={len(residuals)}"
    )
    for gid, res in per_wall:
        lines.append(
            f"    {gid} | mean={res.mean() * 1000:6.2f} mm | "
            f"RMS={np.sqrt(np.mean(res ** 2)) * 1000:6.2f} mm | "
            f"max={res.max() * 1000:6.2f} mm | pts={len(res)}"
        )

    _emit(logger, lines)
