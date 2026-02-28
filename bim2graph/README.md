# BIM2GRAPH

## Overview

BIM2GRAPH converts IFC models into a Neo4j graph.

It reads architectural/structural/MEP IFC files, extracts semantic entities and topology, and writes nodes/relationships using parameterized Cypher queries.

Current implementation is orchestrated in `bim2graph/graph_builder.py` and uses:
- extractors in `bim2graph/extractor/*`
- query loader in `bim2graph/query_manager.py`
- persistence layer in `bim2graph/persistence/neo4j_ops.py`
- Cypher definitions in `query_handler/cypher4bim.cypher`

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

#### Spaces (`extractor/spaces.py`)
- Extract `IfcSpace`
- Properties: `id`, `name`, `longName`, `ifcClass`, `centroid`

#### Walls (`extractor/walls.py`)
- Extract `IfcWall`
- Properties: `id`, `name`, `ifcClass`, `directionSense`, `layerCount`, `axis2`

#### Structural hints (`extractor/walls.py`)
- From optional STR IFC, extract wall-level data for layer enrichment:
	- `loadBearing`, `thickness`, `materials`

#### Layers (`extractor/walls.py`)
- Extract material layers from wall material associations
- Properties: `id`, `wall_id`, `layerIndex`, `loadBearing`, `thickness`, `name`, `ifcClass`

#### Openings (`extractor/openings.py`)
- Extract `IfcOpeningElement` nodes via `IfcRelVoidsElement`
- Create wall-opening edges:
	- `(:Wall)-[:VOIDED_BY]->(:Opening)`

#### Space-wall boundaries (`extractor/relationships.py`)
- Extract via `IfcRelSpaceBoundary`
- Edge payload: `space_id`, `wall_id`, `side`, `boundaryType`

### 3) Extract MEP data (if MEP IFC provided)

In `extractor/mep.py`:
- MEP elements: selected IFC classes (flow segment/fitting/proxy)
- MEP systems: `IfcSystem`
- System memberships: `IfcRelAssignsToGroup`
- MEP-wall relationships:
	- Topology-first (e.g., `IfcRelConnectsElements`, opening-fill chains)
	- Optional geometry fallback (if enabled in code path)
- MEP-system to space relationships from IFC spatial topology

### 4) Persist to Neo4j

In `graph_builder.py` + `persistence/neo4j_ops.py`:

1. Reset and schema:
	 - `RESET_DATABASE`
	 - create uniqueness constraints
2. Upsert nodes:
	 - `Space`, `Wall`, `Layer`, `Opening`, `MEPElement`, `MEPSystem`
3. Create relationships:
	 - `Wall-[:HAS_LAYER]->Layer`
	 - `Wall-[:VOIDED_BY]->Opening`
	 - `Space-[:BOUNDED_BY]->Wall` (with `side`, `boundaryType`)
	 - `MEPSystem-[:CONTAINS]->MEPElement`
	 - `MEPElement-[:PASSES_THROUGH]->Wall`
	 - `MEPSystem-[:VISIBLE_IN]->Space`

---

## Data/Query Layer

Cypher queries are stored in:
- `query_handler/cypher4bim.cypher`

Loaded dynamically by:
- `bim2graph/query_manager.py`

Executed by:
- `bim2graph/persistence/neo4j_ops.py`

---

## How to Run

From project root:
- Ensure Neo4j is running and `.env` has credentials (`NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD`)
- Set IFC paths in `main.py`
- Run `main.py`

`main.py` currently executes:
1. BIM2GRAPH
2. SENSOR2GRAPH

---

## Notes

- This pipeline currently resets the full Neo4j DB each run.
- Logging is optional and routed via the injected `logger`.
- Relation quality depends on IFC export completeness (especially topology relations).

