# bim2graph

## Overview

BIM2GRAPH converts IFC models into a Neo4j graph.

It reads architectural/structural/MEP IFC files, extracts semantic entities and topology, and writes nodes/relationships using parameterized Cypher queries.

Current implementation is orchestrated in `bim2graph/graph_builder.py` and uses:
- extractors in `bim2graph/worker/*`
- geometry/IFC helpers in `bim2graph/worker/util/*`
- query loader in `query_manager/` (shared `QueryManager`)
- persistence layer in `bim2graph/persistence/neo4j_ops.py`
- Cypher definitions in `query_manager/query_handler.cypher`

---

## Module Structure

```
bim2graph/
├── __init__.py                     # Package exports: bim2graph, QueryManager, Neo4jOperations
├── graph_builder.py                # Orchestrator: bim2graph() - load IFC, extract, persist
├── worker/                         # Extraction layer (IFC -> plain dicts)
│   ├── __init__.py                 # Re-exports all extractor / relationship functions
│   ├── spatial_extractor.py        # IfcBuilding, IfcBuildingStorey nodes (+ bbox, center)
│   ├── space_extractor.py          # IfcSpace nodes (+ bbox, centroid)
│   ├── wall_extractor.py           # IfcWall nodes, STR elements, material Layer nodes
│   ├── opening_extractor.py        # IfcOpeningElement nodes via IfcRelVoidsElement
│   ├── mep_extractor.py            # IfcSystem + MEP element nodes (shape type, dimensions)
│   ├── relationship_extractor.py   # All edge payloads (spatial, boundary, penetration, membership)
│   └── util/                       # Stateless helpers shared by the extractors
│       ├── __init__.py             # Re-exports all helper functions
│       ├── geometry.py             # ifcopenshell geometry: bbox, centroid, AABB union/center (mm)
│       ├── wall_util.py            # Placements, material associations, Psets, layer/STR matching
│       ├── mep_util.py             # MEP classification, shape signature/dimensions, swept-solid AABB
│       └── rel_util.py             # Aggregation parents, wall side, AABB intersection/overlap
└── persistence/                    # Persistence layer (dicts -> Neo4j)
    ├── __init__.py                 # Exports Neo4jOperations
    └── neo4j_ops.py                # Neo4jOperations: reset, schema, upsert_*, create_*_rels
```

---

## Inputs

- `arc_path` (required): ARC IFC model
- `str_path` (optional): STR IFC model (for load-bearing inference on layers)
- `mep_path` (optional): MEP IFC model

Entrypoint call:
- `bim2graph(driver, arc_path, str_path=None, mep_path=None, logger=None)`

---

## End-to-End Pipeline

### 1) Initialize

In `graph_builder.py`:
- Create `QueryManager()`
- Create `Neo4jOperations(query_manager, logger)`
- Open IFC files with `ifcopenshell.open(...)`

### 2) Extract ARC/STR data

#### Spaces (`worker/space_extractor.py`)
- Extract `IfcSpace`
- Properties: `id`, `name`, `longName`, `ifcClass`, `centroid`, `bbox_min`, `bbox_max`

#### Walls (`worker/wall_extractor.py`)
- Extract `IfcWall`
- Properties: `id`, `name`, `ifcClass`, `directionSense`, `layerCount`, `axis2`, `center`, `bbox_min`, `bbox_max`

#### Structural hints (`worker/wall_extractor.py`)
- From optional STR IFC, extract wall-level data for layer enrichment:
	- `loadBearing`, `thickness`, `materials`

#### Layers (`worker/wall_extractor.py`)
- Extract material layers from wall material associations
- Properties: `id`, `wall_id`, `layerIndex`, `loadBearing`, `thickness`, `name`, `ifcClass`

#### Openings (`worker/opening_extractor.py`)
- Extract `IfcOpeningElement` nodes via `IfcRelVoidsElement`
- Properties: `id`, `name`, `ifcClass`, `center`

#### Spatial hierarchy (`worker/spatial_extractor.py`, `worker/relationship_extractor.py`)
- Edges first: `IfcRelAggregates` (building-storey) and `IfcRelContainedInSpatialStructure` (storey-space)
- Only storeys that contain spaces are retained; their center is derived from the contained spaces
- Buildings derive their bbox/center from the retained storeys
- Building/Storey properties: `id`, `name`, `ifcClass`, `center`, `bbox_min`, `bbox_max`

#### Space-wall boundaries (`worker/relationship_extractor.py`)
- Extract via `IfcRelSpaceBoundary`
- Edge payload: `space_id`, `wall_id`, `side`, `boundaryType`

### 3) Extract MEP data (if MEP IFC provided)

In `worker/mep_extractor.py` and `worker/util/mep_util.py`:
- MEP elements: selected IFC classes (flow segment/fitting/proxy), classified into `cylindrical` / `rectangular` / `other`
- Properties: `id`, `name`, `ifcClass`, `shapeType`, `radius`, `length`, `sizeX/Y/Z`, `center`, `axisX`, `direction`, `bbox_min`, `bbox_max`
- MEP systems: `IfcSystem`
- System memberships: `IfcRelAssignsToGroup`
- MEP-wall relationships: AABB intersection between the swept-solid MEP AABB and the wall AABB, with penetration geometry from the overlap box
- MEP-space relationships: AABB intersection between MEP element and space

### 4) Persist to Neo4j

In `graph_builder.py` + `persistence/neo4j_ops.py`:

1. Reset and schema:
	 - `RESET_DATABASE`
	 - create uniqueness constraints
2. Upsert nodes:
	 - `Building`, `Storey`, `Space`, `Wall`, `Layer`, `Opening`, `MEPElement`, `MEPSystem`
3. Create relationships:
	 - `Building-[:HAS_STOREY]->Storey`
	 - `Storey-[:HAS_SPACE]->Space`
	 - `Space-[:BOUNDED_BY]->Wall` (with `side`, `boundaryType`)
	 - `Space-[:INTERSECTS]->MEPElement`
	 - `Wall-[:HAS_LAYER]->Layer`
	 - `Wall-[:VOIDED_BY]->Opening`
	 - `MEPSystem-[:CONTAINS]->MEPElement`
	 - `Wall-[:PENETRATED_BY]->MEPElement` (with penetration geometry)

---

## Data/Query Layer

Cypher queries are stored in:
- `query_manager/query_handler.cypher`

Loaded dynamically by:
- `query_manager/` (shared `QueryManager`)

Executed by:
- `bim2graph/persistence/neo4j_ops.py`
