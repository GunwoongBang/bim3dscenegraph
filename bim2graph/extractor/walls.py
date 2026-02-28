"""
Wall and layer extraction from IFC models.
"""

from typing import Any, Optional

from . import geometry
from .ifc_utils import get_pset_property, get_material_association


def get_material_info(element) -> tuple[Optional[str], int, Optional[str]]:
    """
    Extract material layer set information from an element.

    Args:
        element: IFC element with HasAssociations

    Returns:
        Tuple:
        (direction_sense, layer_count, material_type) where:
            - direction_sense: "POSITIVE" or "NEGATIVE" (from IfcMaterialLayerSetUsage)
            - layer_count: Number of material layers
            - material_type: Type of material definition found
    """
    material_def, material_layers = get_material_association(element)

    if material_def is None:
        return None, 0, None

    direction_sense = None
    layer_count = 0
    material_type = material_def.is_a()

    if material_def.is_a("IfcMaterialLayerSetUsage"):
        direction_sense = getattr(material_def, "DirectionSense", None)
        if material_layers:
            layer_count = len(material_layers)

    elif material_def.is_a("IfcMaterialLayerSet"):
        if material_layers:
            layer_count = len(material_layers)

    elif material_def.is_a("IfcMaterialList"):
        if hasattr(material_def, "Materials"):
            layer_count = len(material_def.Materials)

    elif material_def.is_a("IfcMaterial"):
        layer_count = 1

    return direction_sense, layer_count, material_type


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
            - directionSense: Layer direction from material usage
            - layerCount: Number of material layers
            - axis2: Layer stratification direction vector
            - center: Wall geometric center in millimeters
    """
    walls = []

    for wall in model.by_type("IfcWall"):
        # Extract geometry
        bbox = geometry.extract_bbox(wall)
        center = geometry.extract_centroid(wall)

        # Only need axis2 for layer direction
        _, axis2 = geometry.extract_placement(wall)

        if bbox is None and logger:
            logger.logText(
                "BIM2GRAPH",
                f"Geometry extraction failed for wall {wall.GlobalId}"
            )

        # Extract material info
        direction_sense, layer_count, _ = get_material_info(wall)

        wall_data = {
            "id": wall.GlobalId,
            "name": getattr(wall, "Name", None) or "Unknown",
            "ifcClass": wall.is_a(),
            "bbox_min": bbox[0] if bbox else None,
            "bbox_max": bbox[1] if bbox else None,
            "directionSense": direction_sense,
            "layerCount": layer_count,
            "axis2": axis2,
        }
        walls.append(wall_data)

    if logger:
        logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")

    return walls


def get_material_layers(element) -> list[dict]:
    """
    Extract individual material layer details from an element.

    Args:
        element: IFC element with HasAssociations (typically IfcWall)

    Returns:
        List of dicts with keys:
            - thickness: Layer thickness in model units
            - name: Material name
            - index: Layer position (0-based)
        Returns empty list if no layers found.
    """
    _, material_layers = get_material_association(element)

    if not material_layers:
        return []

    layers = []
    for i, mat_layer in enumerate(material_layers):
        mat_name = None
        if mat_layer.Material:
            mat_name = getattr(mat_layer.Material, "Name", None)
        layers.append({
            "thickness": getattr(mat_layer, "LayerThickness", None),
            "name": mat_name,
            "index": i
        })
    return layers


def get_layer_info(element) -> tuple[Optional[float], Optional[list[str]]]:
    """
    Extract aggregated layer info from a wall element.

    Args:
        element: IFC wall element

    Returns:
        Tuple (total_thickness, material_names_list) or (None, None) if not available
    """
    layers = get_material_layers(element)
    if not layers:
        return None, None

    thickness = sum(layer["thickness"] or 0 for layer in layers)
    mat_names = [layer["name"] for layer in layers if layer["name"]]
    return thickness, mat_names


def match_layer_to_str(
    layer_thickness: Optional[float],
    mat_name: Optional[str],
    str_elements: list[dict]
) -> Optional[bool]:
    """
    Match a layer to structural elements by thickness and material name.

    Args:
        layer_thickness: Layer thickness in model units
        mat_name: Material name
        str_elements: List of structural element dicts from extract_str_elements

    Returns:
        loadBearing value (True/False) if matched, None otherwise
    """
    if not str_elements or layer_thickness is None:
        return None

    for str_elem in str_elements:
        if (str_elem["thickness"] == layer_thickness and
                mat_name in str_elem["materials"]):
            return str_elem["loadBearing"]

    return None


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
        wall.GlobalId: wall
        for wall in model.by_type("IfcWall")
    }

    for wall_id, ifc_wall in ifc_walls.items():
        if wall_id not in wall_ids:
            continue

        material_layers = get_material_layers(ifc_wall)

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
            "BIM2GRAPH", f"{len(layers)} Wall-Layer elements extracted")

    return layers


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

    for elem in str_model.by_type("IfcWall"):
        # Extract load bearing info for walls
        load_bearing = get_pset_property(elem, "LoadBearing")
        bbox = geometry.extract_bbox(elem)
        thickness, mat_names = get_layer_info(elem)

        str_elements.append({
            "id": elem.GlobalId,
            "loadBearing": load_bearing,
            "thickness": thickness,
            "materials": mat_names or [],
            "bbox_min": bbox[0] if bbox else None,
            "bbox_max": bbox[1] if bbox else None,
        })

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(str_elements)} structural wall elements extracted")

    return str_elements
