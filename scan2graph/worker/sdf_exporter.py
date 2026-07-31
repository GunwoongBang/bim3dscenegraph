"""
SDF world model generation for IFC models.
"""

from pathlib import Path

import xml.etree.ElementTree as ET

from .util import (
    extract_mesh_from_shape,
    safe_name,
    write_obj,
    pretty_xml,
)


SUPPORTED_TYPES = ["IfcWall", "IfcSlab"]


def export_ifc_to_sdf(ifc_model, logger=None):
    """
    Export IFC walls/slabs as mesh visuals to a single SDF world file.

    Args:
        ifc_model: Open ifcopenshell model
        logger: Optional logger with logText(category, message)
    """
    model_name = "ifc_world"
    output_path = (
        Path(__file__).parent.parent
        / "ifc2pointcloud" / "src" / "robot_gazebo" / "worlds" / "ifc_world.sdf"
    ).resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    sdf = ET.Element("sdf", version="1.6")
    world = ET.SubElement(sdf, "world", name=f"{model_name}")

    # World defaults for Gazebo simulation and virtual scanning.
    include_ground = ET.SubElement(world, "include")
    ET.SubElement(include_ground, "uri").text = "model://ground_plane"

    include_sun = ET.SubElement(world, "include")
    ET.SubElement(include_sun, "uri").text = "model://sun"

    physics = ET.SubElement(world, "physics", type="ode")
    ET.SubElement(physics, "real_time_update_rate").text = "1000.0"
    ET.SubElement(physics, "max_step_size").text = "0.001"
    ET.SubElement(physics, "real_time_factor").text = "1"

    ode = ET.SubElement(physics, "ode")
    solver = ET.SubElement(ode, "solver")
    ET.SubElement(solver, "type").text = "quick"
    ET.SubElement(solver, "iters").text = "150"
    ET.SubElement(solver, "precon_iters").text = "0"
    ET.SubElement(solver, "sor").text = "1.4"
    ET.SubElement(solver, "use_dynamic_moi_rescaling").text = "1"

    constraints = ET.SubElement(ode, "constraints")
    ET.SubElement(constraints, "cfm").text = "0.00001"
    ET.SubElement(constraints, "erp").text = "0.2"
    ET.SubElement(constraints, "contact_max_correcting_vel").text = "2000.0"
    ET.SubElement(constraints, "contact_surface_layer").text = "0.01"

    include_robot = ET.SubElement(world, "include")
    ET.SubElement(include_robot, "name").text = "robot"
    ET.SubElement(include_robot, "uri").text = "model://robot"
    ET.SubElement(
        include_robot, "pose").text = "-1.5 3 0.7 3.141592654 0 3.141592654"
    ET.SubElement(include_robot, "static").text = "false"

    mesh_dir = output_path.parent / f"{model_name}_meshes"
    mesh_dir.mkdir(parents=True, exist_ok=True)

    for ifc_type in SUPPORTED_TYPES:
        try:
            elements = ifc_model.by_type(ifc_type)
        except RuntimeError:
            # The requested entity may not exist in some IFC schemas.
            continue
        if not elements:
            continue

        for element in elements:
            try:
                vertices, faces, _ = extract_mesh_from_shape(element)
            except Exception:
                continue

            if vertices.size == 0 or faces.size == 0:
                continue

            # Skip degenerate geometry.
            if len(vertices) < 3 or len(faces) < 1:
                continue

            global_id = getattr(element, "GlobalId", "unknown")
            model_id = safe_name(global_id)
            model_name_for_sdf = f"{ifc_type}_{model_id}"

            mesh_name = f"{model_name_for_sdf}.obj"
            mesh_path = mesh_dir / mesh_name
            write_obj(mesh_path, vertices, faces)

            model_node = ET.SubElement(world, "model", name=model_name_for_sdf)
            ET.SubElement(model_node, "static").text = "true"
            ET.SubElement(model_node, "pose").text = "0 0 0 0 0 0"

            link = ET.SubElement(model_node, "link", name="link")

            collision = ET.SubElement(link, "collision", name="collision")
            collision_geometry = ET.SubElement(collision, "geometry")
            collision_mesh = ET.SubElement(collision_geometry, "mesh")
            ET.SubElement(collision_mesh, "uri").text = str(
                mesh_path.as_posix())
            ET.SubElement(collision_mesh, "scale").text = "1 1 1"

            visual = ET.SubElement(link, "visual", name="visual")
            geometry = ET.SubElement(visual, "geometry")
            mesh = ET.SubElement(geometry, "mesh")
            ET.SubElement(mesh, "uri").text = str(mesh_path.as_posix())
            ET.SubElement(mesh, "scale").text = "1 1 1"

            # Optional: mild color by type for quick visual distinction.
            material = ET.SubElement(visual, "material")
            if ifc_type == "IfcWall":
                ET.SubElement(material, "ambient").text = "0.70 0.70 0.70 1"
                ET.SubElement(material, "diffuse").text = "0.75 0.75 0.75 1"
            elif ifc_type == "IfcSlab":
                ET.SubElement(material, "ambient").text = "0.60 0.60 0.65 1"
                ET.SubElement(material, "diffuse").text = "0.65 0.65 0.70 1"
            else:
                ET.SubElement(material, "ambient").text = "0.50 0.65 0.85 1"
                ET.SubElement(material, "diffuse").text = "0.55 0.70 0.90 1"

    output_path.write_text(pretty_xml(sdf), encoding="utf-8")

    if logger:
        logger.logText("SCAN2GRAPH", "IFC to SDF export completed")
