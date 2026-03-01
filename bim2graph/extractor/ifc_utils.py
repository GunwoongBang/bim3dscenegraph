"""
Shared IFC utilities for property and material extraction.

Provides common functions for working with IFC elements across different extractors.
"""

from typing import Any, Optional


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
