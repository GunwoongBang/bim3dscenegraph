# MEP element types to extract
MEP_TYPES = [
    "IfcFlowSegment",           # Pipes
    "IfcFlowFitting",           # Elbows, tees, etc.
    "IfcBuildingElementProxy",  # Switches, receptacles, panelboards
]


def classify_mep_element(element):
    representation = getattr(element, "Representation", None)
    reps = getattr(representation, "Representations", None)

    for rep in reps:
        items = getattr(rep, "Items", None)

        for item in items:
            if item.is_a("IfcExtrudedAreaSolid"):
                return item
            if item.is_a("IfcMappedItem"):
                mapping_source = getattr(item, "MappingSource", None)
                mapped_rep = getattr(
                    mapping_source, "MappedRepresentation", None) if mapping_source else None
                mapped_items = getattr(mapped_rep, "Items", None) or []
                for mapped_item in mapped_items:
                    if mapped_item.is_a("IfcExtrudedAreaSolid"):
                        return mapped_item

    return None


def extract_shape_signature(element):
    item = classify_mep_element(element)

    # elements out of scope (e.g. tee, elbow, etc.)
    if item is None:
        return {
            "shapeType": "other",
            "radiusMm": None,
        }

    if item.is_a("IfcExtrudedAreaSolid"):
        swept = getattr(item, "SweptArea", None)

        # cylindrical elements (pipes)
        if swept and swept.is_a("IfcCircleProfileDef"):
            radius = getattr(swept, "Radius", None)

            return {
                "shapeType": "cylindrical",
                "radiusMm": radius,
            }
        # rectangular elements (switches, receptacles, panelboards)
        if swept and swept.is_a("IfcRectangleProfileDef"):
            return {
                "shapeType": "rectangular",
                "radiusMm": None,
            }

    return {
        "shapeType": "other",
        "radiusMm": None,
    }
