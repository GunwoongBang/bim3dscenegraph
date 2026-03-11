"""
Wall and layer extraction from IFC models.
"""

from typing import Optional

from .utils.wall_util import get_material_info, get_pset_property, get_layer_info, get_material_layers, match_layer_to_str
from .geometry import extract_bbox, extract_centroid, extract_placement


def extract_walls(model, logger=None) -> list[dict]:
    """
    Extract all walls from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
        walls:
        List of wall dictionaries with keys:
            - id: GlobalId
            - name: Wall name
            - ifcClass: IFC class type
            - loadBearing: Boolean or None
            - isExternal: Boolean or None
            - bbox_min, bbox_max: Bounding box in millimeters
            - center: Wall geometric center in millimeters
            - directionSense: Layer direction from material usage
            - layerCount: Number of material layers
            - axis2: Layer stratification direction vector
    """
    walls = []

    ifc_walls = model.by_type("IfcWall")

    if not ifc_walls:
        if logger:
            logger.logText("BIM2GRAPH", "No IfcWall entities found in model")

        return walls

    for wall in ifc_walls:
        # Extract geometry
        bbox = extract_bbox(wall)
        center = extract_centroid(wall)

        # Only need axis2 for layer direction
        _, axis2 = extract_placement(wall)

        # Extract material info
        direction_sense, layer_count, _ = get_material_info(wall)

        wall_data = {
            "id": wall.GlobalId,
            "name": getattr(wall, "Name", None) or "Unknown",
            "ifcClass": wall.is_a(),
            "bbox_min": bbox[0] if bbox else None,
            "bbox_max": bbox[1] if bbox else None,
            "center": center,
            "directionSense": direction_sense,
            "layerCount": layer_count,
            "axis2": axis2,
        }
        walls.append(wall_data)

    if logger:
        logger.logText("BIM2GRAPH", f"Extracted {len(walls)} Wall elements")

    return walls


def extract_str_elements(str_model, logger=None) -> list[dict]:
    """
    Extract structural elements from the STR model and return a list of updates.

    Args:
        str_model: ifcopenshell model instance of the STR file
        logger: Optional logger for output messages

    Returns:
        str_elements:
        List of structural elements with properties relevant for updating layer nodes in the graph.
    """
    if str_model is None:
        return []

    str_elements = []

    ifc_str_walls = str_model.by_type("IfcWall")

    if not ifc_str_walls:
        if logger:
            logger.logText(
                "BIM2GRAPH", "No IfcWall entities found in STR model")

        return str_elements

    for elem in ifc_str_walls:
        # Extract load bearing info for walls
        load_bearing = get_pset_property(elem, "LoadBearing")
        # bbox = extract_bbox(elem)
        thickness, mat_names = get_layer_info(elem)

        str_elements.append({
            "id": elem.GlobalId,
            "loadBearing": load_bearing,
            "thickness": thickness,
            "materials": mat_names or [],
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(str_elements)} Structural wall elements")

    return str_elements


def extract_layers(
    model,
    walls: list[dict],
    str_elements: Optional[list[dict]] = None,
    logger=None
) -> list[dict]:
    """
    Extract all material layers from walls.

    Args:
        model: ifcopenshell model instance
        walls: List of wall dictionaries (from extract_walls)
        str_elements: Pre-extracted structural elements (from extract_str_elements), optional
        logger: Optional logger for output messages

    Returns:
        layers:
        List of layer dictionaries with keys:
            - id: Composite id (wall_id + layer index)
            - wall_id: Parent wall GlobalId
            - layerIndex: Position in layer stack (0=first)
            - loadBearing: Boolean or None (from STR matching)
            - thickness: Layer thickness in model units
            - name: Material name
            - ifcClass: Always "IfcMaterialLayer"
    """
    layers = []
    wall_ids = {w["id"] for w in walls}
    str_elements = str_elements or []

    # Build lookup of IFC wall objects
    ifc_walls = {
        wall.GlobalId: wall for wall in model.by_type("IfcWall")
    }

    # items() returns key-value pairs of (GlobalId, wall object) according to ifc_walls (line: 142)
    for wall_id, ifc_wall in ifc_walls.items():
        if wall_id not in wall_ids:
            continue

        material_layers = get_material_layers(ifc_wall)

        if not material_layers:
            if logger:
                logger.logText(
                    "BIM2GRAPH", f"No material layers found for wall {wall_id}")
            continue

        for layer in material_layers:
            mat_name = layer["name"]
            layer_thickness = layer["thickness"]
            layer_index = layer["index"]

            # Match with STR elements
            layer_load_bearing = match_layer_to_str(
                layer_thickness, mat_name, str_elements
            )

            layer_data = {
                "id": f"{wall_id}_layer_{layer_index}",
                "wall_id": wall_id,
                "layerIndex": layer_index,
                "loadBearing": layer_load_bearing,
                "thickness": layer_thickness,
                "name": mat_name or f"Layer {layer_index}",
                "ifcClass": "IfcMaterialLayer"
            }
            layers.append(layer_data)

    if logger:
        logger.logText(
            "BIM2GRAPH", f"Extracted {len(layers)} Layer elements")

    return layers
