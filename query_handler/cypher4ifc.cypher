-- name: RESET_DATABASE
MATCH (n)
DETACH DELETE n

-- name: ENSURE_SCHEMA_SPACES
CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) REQUIRE s.id IS UNIQUE

-- name: ENSURE_SCHEMA_WALLS
CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE

-- name: ENSURE_SCHEMA_LAYERS
CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (l:Layer) REQUIRE l.id IS UNIQUE

-- name: ENSURE_SCHEMA_OPENINGS
CREATE CONSTRAINT opening_id IF NOT EXISTS FOR (o:Opening) REQUIRE o.id IS UNIQUE

-- name: ENSURE_SCHEMA_MEP_SYSTEM
CREATE CONSTRAINT mep_system_id IF NOT EXISTS FOR (ms:MEPSystem) REQUIRE ms.id IS UNIQUE

-- name: ENSURE_SCHEMA_MEP_ELEMENT
CREATE CONSTRAINT mep_element_id IF NOT EXISTS FOR (me:MEPElement) REQUIRE me.id IS UNIQUE

-- name: UPSERT_SPACES
UNWIND $spaces AS space
MERGE (s:Space { id: space.id })
SET s.name = space.name,
    s.longName = space.longName,
    s.ifcClass = space.ifcClass,
    s.centroid = space.centroid

-- name: UPSERT_WALLS
UNWIND $walls AS wall
MERGE (w:Wall { id: wall.id })
SET w.name = wall.name,
    w.ifcClass = wall.ifcClass,
    w.loadBearing = wall.loadBearing,
    w.isExternal = wall.isExternal,
    w.directionSense = wall.directionSense,
    w.layerCount = wall.layerCount,
    w.axis2 = wall.axis2,
    w.center = wall.center,
    w.bbox_min = wall.bbox_min,
    w.bbox_max = wall.bbox_max

-- name: UPSERT_LAYERS
UNWIND $layers AS layer
MERGE (l:Layer { id: layer.id })
SET l.name = layer.name,
    l.ifcClass = layer.ifcClass,
    l.layerIndex = layer.layerIndex,
    l.loadBearing = layer.loadBearing,
    l.thickness = layer.thickness

-- name: UPSERT_OPENINGS
UNWIND $openings AS opening
MERGE (o:Opening { id: opening.id })
SET o.name = opening.name,
    o.ifcClass = opening.ifcClass,
    o.center = opening.center

-- name: UPSERT_MEP_SYSTEMS
UNWIND $systems AS sys
MERGE (ms:MEPSystem { id: sys.id })
SET ms.name = sys.name,
    ms.ifcClass = sys.ifcClass

-- name: UPSERT_MEP_ELEMENTS
UNWIND $elements AS elem
MERGE (me:MEPElement { id: elem.id })
SET me.name = elem.name,
    me.ifcClass = elem.ifcClass,
    me.shapeType = elem.shapeType,
    me.penetrationCenter = elem.penetrationCenter,
    me.penetrationLengthMm = elem.penetrationLengthMm,
    me.penetrationSizeXmm = elem.penetrationSizeXmm,
    me.penetrationSizeYmm = elem.penetrationSizeYmm,
    me.penetrationSizeZmm = elem.penetrationSizeZmm

-- name: CREATE_SPACE_WALL_EDGES
UNWIND $edges AS edge
MATCH (s:Space { id: edge.space_id })
MATCH (w:Wall { id: edge.wall_id })
MERGE (s)-[r:BOUNDED_BY]->(w)
SET r.side = edge.side,
    r.boundaryType = edge.boundaryType

-- name: CREATE_WALL_LAYER_EDGES
UNWIND $layers AS layer
MATCH (w:Wall { id: layer.wall_id })
MATCH (l:Layer { id: layer.id })
MERGE (w)-[:HAS_LAYER]->(l)

-- name: CREATE_WALL_OPENING_EDGES
UNWIND $edges AS edge
MATCH (w:Wall { id: edge.wall_id })
MATCH (o:Opening { id: edge.opening_id })
MERGE (w)-[:VOIDED_BY]->(o)

-- name: CREATE_MEP_SYSTEM_MEP_ELEMENT_EDGES
UNWIND $edges AS edge
MATCH (ms:MEPSystem { id: edge.system_id })
MATCH (me:MEPElement { id: edge.mep_id })
MERGE (ms)-[:CONTAINS]->(me)

-- name: CREATE_MEP_SYSTEM_SPACE_EDGES
UNWIND $edges AS edge
MATCH (ms:MEPSystem { id: edge.system_id })
MATCH (s:Space { id: edge.space_id })
MERGE (ms)-[r:VISIBLE_IN]->(s)
SET r.source = edge.source

-- name: CREATE_MEP_ELEMENT_WALL_EDGES
UNWIND $edges AS edge
MATCH (me:MEPElement { id: edge.mep_id })
MATCH (w:Wall { id: edge.wall_id })
WITH me, w, edge
WHERE edge.relationship = 'PASSES_THROUGH'
MERGE (me)-[r:PASSES_THROUGH]->(w)
SET r.source = edge.source,
    r.penetrationCenter = edge.penetrationCenter,
    r.radiusMm = edge.radiusMm,
    r.penetrationLengthMm = edge.penetrationLengthMm,
    r.penetrationSizeXmm = edge.penetrationSizeXmm,
    r.penetrationSizeYmm = edge.penetrationSizeYmm,
    r.penetrationSizeZmm = edge.penetrationSizeZmm
