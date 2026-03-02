"""
Shared IFC helpers for wall extraction.

Provides utility functions used by walls.py for property and material extraction.
"""

from typing import Any, Optional


def get_material_association(element):
    """
    Get the material definition associated with an IFC element.

    Args:
        element: IFC element with HasAssociations

    Returns:
        Tuple:
        (material_def, material_layers) where:
            - material_def: The IfcMaterialLayerSetUsage, IfcMaterialLayerSet, etc.
            - material_layers: List of IfcMaterialLayer objects, or None
        Returns (None, None) if no material association found.
    """
    for assoc in getattr(element, "HasAssociations", []):
        if not assoc.is_a("IfcRelAssociatesMaterial"):
            continue

        material = assoc.RelatingMaterial
        material_layers = None

        if material.is_a("IfcMaterialLayerSetUsage"):
            layer_set = material.ForLayerSet
            if layer_set:
                material_layers = getattr(layer_set, "MaterialLayers", [])
            return material, material_layers

        # elif material.is_a("IfcMaterialLayerSet"):
        #     material_layers = getattr(material, "MaterialLayers", [])
        #     return material, material_layers

        # elif material.is_a("IfcMaterialList"):
        #     return material, None

        elif material.is_a("IfcMaterial"):
            return material, None

    return None, None


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

    # elif material_def.is_a("IfcMaterialLayerSet"):
    #     if material_layers:
    #         layer_count = len(material_layers)

    # elif material_def.is_a("IfcMaterialList"):
    #     if hasattr(material_def, "Materials"):
    #         layer_count = len(material_def.Materials)

    elif material_def.is_a("IfcMaterial"):
        layer_count = 1

    return direction_sense, layer_count, material_type


def get_pset_property(element, prop_name: str, pset_name: Optional[str] = None) -> Any:
    """
    Extract a property value from an IFC element's property sets.

    Args:
        element: IFC element with IsDefinedBy relationships
        prop_name: Name of the property to find
        pset_name: Optional specific property set name to search in

    Returns:
        Property value (unwrapped if IfcValue), or None if not found
    """
    for rel in getattr(element, "IsDefinedBy", []):
        if not rel.is_a("IfcRelDefinesByProperties"):
            continue

        pset = rel.RelatingPropertyDefinition
        if not pset.is_a("IfcPropertySet"):
            continue

        if pset_name and pset.Name != pset_name:
            continue

        for prop in getattr(pset, "HasProperties", []):
            if prop.is_a("IfcPropertySingleValue") and prop.Name == prop_name:
                val = getattr(prop, "NominalValue", None)
                if val is not None:
                    return val.wrappedValue if hasattr(val, "wrappedValue") else val

    return None


def get_layer_info(element) -> tuple[Optional[float], Optional[list[str]]]:
    """
    Extract aggregated layer info from a wall element.

    Args:
        element: IFC wall element

    Returns:
        Tuple:
        (total_thickness, material_names_list) or (None, None) if not available
    """
    layers = get_material_layers(element)
    if not layers:
        return None, None

    thickness = sum(layer["thickness"] or 0 for layer in layers)
    mat_names = [layer["name"] for layer in layers if layer["name"]]
    return thickness, mat_names


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
            "name": mat_name,
            "thickness": getattr(mat_layer, "LayerThickness", None),
            "index": i
        })
    return layers


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
