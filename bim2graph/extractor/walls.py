"""
Wall and layer extraction from IFC models.
"""

from . import geometry


def get_pset_property(element, prop_name, pset_name=None):
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


def get_material_info(element):
    """
    Extract material layer set information from an element.

    Args:
        element: IFC element with HasAssociations

    Returns:
        Tuple (direction_sense, layer_count, material_type) where:
            - direction_sense: "POSITIVE" or "NEGATIVE" (from IfcMaterialLayerSetUsage)
            - layer_count: Number of material layers
            - material_type: Type of material definition found
    """
    direction_sense = None
    layer_count = 0
    material_type = None

    for assoc in getattr(element, "HasAssociations", []):
        if not assoc.is_a("IfcRelAssociatesMaterial"):
            continue

        material = assoc.RelatingMaterial

        if material.is_a("IfcMaterialLayerSetUsage"):
            direction_sense = getattr(material, "DirectionSense", None)
            layer_set = material.ForLayerSet
            if layer_set and hasattr(layer_set, "MaterialLayers"):
                layer_count = len(layer_set.MaterialLayers)
            material_type = "IfcMaterialLayerSetUsage"
            break

        elif material.is_a("IfcMaterialLayerSet"):
            if hasattr(material, "MaterialLayers"):
                layer_count = len(material.MaterialLayers)
            material_type = "IfcMaterialLayerSet"
            break

        elif material.is_a("IfcMaterialList"):
            if hasattr(material, "Materials"):
                layer_count = len(material.Materials)
            material_type = "IfcMaterialList"
            break

        elif material.is_a("IfcMaterial"):
            layer_count = 1
            material_type = "IfcMaterial"
            break

    return direction_sense, layer_count, material_type


def extract_walls(model, logger=None):
    """
    Extract all walls from the IFC model.

    Args:
        model: ifcopenshell model instance
        logger: Optional logger for output messages

    Returns:
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
            - origin: Wall reference point in millimeters
    """
    walls = []

    for wall in model.by_type("IfcWall"):
        # Extract geometry
        bbox = geometry.extract_bbox(wall)
        origin, axis2 = geometry.extract_placement(wall)

        if bbox is None and logger:
            logger.logText(
                "BIM2GRAPH",
                f"Geometry extraction failed for wall {wall.GlobalId}"
            )

        # Extract properties
        load_bearing = get_pset_property(wall, "LoadBearing")
        is_external = get_pset_property(wall, "IsExternal")

        # Extract material info
        direction_sense, layer_count, _ = get_material_info(wall)

        wall_data = {
            "id": wall.GlobalId,
            "name": getattr(wall, "Name", None) or "Unknown",
            "ifcClass": wall.is_a(),
            "loadBearing": load_bearing,
            "isExternal": is_external,
            "bbox_min": bbox[0] if bbox else None,
            "bbox_max": bbox[1] if bbox else None,
            "directionSense": direction_sense,
            "layerCount": layer_count,
            "axis2": axis2,
            "origin": origin
        }
        walls.append(wall_data)

    if logger:
        logger.logText("BIM2GRAPH", f"{len(walls)} Wall elements extracted")

    return walls


def extract_layers(model, walls, logger=None):
    """
    Extract all material layers from walls.

    Args:
        model: ifcopenshell model instance
        walls: List of wall dictionaries (from extract_walls)
        logger: Optional logger for output messages

    Returns:
        List of layer dictionaries with keys:
            - id: Composite id (wall_id + layer index)
            - wall_id: Parent wall GlobalId
            - layerIndex: Position in layer stack (0 = first)
            - thickness: Layer thickness in model units
            - name: Material name
            - ifcClass: Always "IfcMaterialLayer"
    """
    layers = []
    wall_ids = {w["id"] for w in walls}

    # Build lookup of IFC wall objects
    ifc_walls = {
        wall.GlobalId: wall
        for wall in model.by_type("IfcWall")
    }

    for wall_id, ifc_wall in ifc_walls.items():
        if wall_id not in wall_ids:
            continue

        for assoc in getattr(ifc_wall, "HasAssociations", []):
            if not assoc.is_a("IfcRelAssociatesMaterial"):
                continue

            material = assoc.RelatingMaterial
            material_layers = None

            if material.is_a("IfcMaterialLayerSetUsage"):
                # Validate layer direction
                layer_direction = getattr(material, "LayerSetDirection", None)
                if layer_direction and layer_direction != "AXIS2" and logger:
                    logger.logText(
                        "BIM2GRAPH",
                        f"Warning: Wall {ifc_wall.Name} ({wall_id}) has layers "
                        f"stratified along {layer_direction} instead of AXIS2"
                    )

                layer_set = material.ForLayerSet
                if layer_set:
                    material_layers = getattr(layer_set, "MaterialLayers", [])

            elif material.is_a("IfcMaterialLayerSet"):
                material_layers = getattr(material, "MaterialLayers", [])

            if material_layers:
                for i, mat_layer in enumerate(material_layers):
                    mat_name = None
                    if mat_layer.Material:
                        mat_name = getattr(mat_layer.Material, "Name", None)

                    layer_data = {
                        "id": f"{wall_id}_layer_{i}",
                        "wall_id": wall_id,
                        "layerIndex": i,
                        "thickness": getattr(mat_layer, "LayerThickness", None),
                        "name": mat_name or f"Layer {i}",
                        "ifcClass": "IfcMaterialLayer"
                    }
                    layers.append(layer_data)
                break  # Only process first material association

    if logger:
        logger.logText(
            "BIM2GRAPH", f"{len(layers)} Wall Layer elements extracted")

    return layers
