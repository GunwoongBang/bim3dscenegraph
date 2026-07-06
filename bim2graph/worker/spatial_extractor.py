"""
Spatial structure extraction (Building, Storey) from IFC models.
"""


def extract_buildings(arc_model, logger=None) -> list[dict]:
    """
    Extract all buildings from the IFC model.

    Returns:
        List of building dictionaries with keys:
            - id: GlobalId
    """
    buildings = [
        {"id": b.GlobalId, "ifcClass": b.is_a()}
        for b in arc_model.by_type("IfcBuilding")
    ]

    if logger:
        logger.logText("BIM2GRAPH", f"Extracted {len(buildings)} Building elements")

    return buildings


def extract_storeys(arc_model, logger=None) -> list[dict]:
    """
    Extract all building storeys from the IFC model.

    Returns:
        List of storey dictionaries with keys:
            - id: GlobalId
    """
    storeys = [
        {"id": s.GlobalId, "ifcClass": s.is_a()}
        for s in arc_model.by_type("IfcBuildingStorey")
    ]

    if logger:
        logger.logText("BIM2GRAPH", f"Extracted {len(storeys)} Storey elements")

    return storeys
