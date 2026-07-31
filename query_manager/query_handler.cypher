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

// BIM2GRAPH Cypher queries
//  Nodes
-- name: UPSERT_BUILDING
UNWIND $buildings AS building
MERGE (b:Building { id: building.id })
SET b.name = building.name,
    b.ifcClass = building.ifcClass,
    b.center = building.center

-- name: UPSERT_STOREYS
UNWIND $storeys AS storey
MERGE (s:Storey { id: storey.id })
SET s.name = storey.name,
    s.ifcClass = storey.ifcClass,
    s.center = storey.center

-- name: UPSERT_SPACES
UNWIND $spaces AS space
MERGE (s:Space { id: space.id })
SET s.name = space.name,
    s.longName = space.longName,
    s.ifcClass = space.ifcClass,
    s.centroid = space.centroid,
    s.bbox_min = space.bbox_min,
    s.bbox_max = space.bbox_max

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
UNWIND $mep_systems AS mep_sys
MERGE (ms:MEPSystem { id: mep_sys.id })
SET ms.name = mep_sys.name,
    ms.ifcClass = mep_sys.ifcClass

-- name: UPSERT_MEP_ELEMENTS
UNWIND $mep_elements AS mep_elem
MERGE (me:MEPElement { id: mep_elem.id })
SET me.name = mep_elem.name,
    me.ifcClass = mep_elem.ifcClass,
    me.shapeType = mep_elem.shapeType,
    me.center = mep_elem.center,
    me.bbox_min = CASE WHEN mep_elem.shapeType = 'other' THEN mep_elem.bbox_min ELSE null END,
    me.bbox_max = CASE WHEN mep_elem.shapeType = 'other' THEN mep_elem.bbox_max ELSE null END,
    me.radius = mep_elem.radius,
    me.length = mep_elem.length,
    me.sizeX = mep_elem.sizeX,
    me.sizeY = mep_elem.sizeY,
    me.sizeZ = mep_elem.sizeZ,
    me.axisX = mep_elem.axisX,
    me.direction = mep_elem.direction

// Edges
-- name: CREATE_BUILDING_STOREY_EDGES
UNWIND $edges AS edge
MATCH (b:Building { id: edge.building_id })
MATCH (s:Storey { id: edge.storey_id })
MERGE (b)-[:HAS_STOREY]->(s)

-- name: CREATE_STOREY_SPACE_EDGES
UNWIND $edges AS edge
MATCH (s:Storey { id: edge.storey_id })
MATCH (sp:Space { id: edge.space_id })
MERGE (s)-[:HAS_SPACE]->(sp)

-- name: CREATE_SPACE_WALL_EDGES
UNWIND $edges AS edge
MATCH (s:Space { id: edge.space_id })
MATCH (w:Wall { id: edge.wall_id })
MERGE (s)-[b:BOUNDED_BY]->(w)
SET b.side = edge.side,
    b.boundaryType = edge.boundaryType

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
MATCH (ms:MEPSystem { id: edge.mep_system_id })
MATCH (me:MEPElement { id: edge.mep_element_id })
MERGE (ms)-[:CONTAINS]->(me)

-- name: CREATE_MEP_ELEMENT_SPACE_EDGES
UNWIND $edges AS edge
MATCH (me:MEPElement { id: edge.mep_element_id })
MATCH (s:Space { id: edge.space_id })
MERGE (s)-[:INTERSECTS]->(me)

-- name: CREATE_MEP_ELEMENT_WALL_EDGES
UNWIND $edges AS edge
MATCH (me:MEPElement { id: edge.mep_element_id })
MATCH (w:Wall { id: edge.wall_id })
WITH me, w, edge
MERGE (w)-[b:PENETRATED_BY]->(me)
SET b.source = edge.source,
    b.penetrationCenter = edge.penetrationCenter,
    b.penetrationRadius = edge.penetrationRadius,
    b.penetrationLength = edge.penetrationLength,
    b.penetrationSizeX = edge.penetrationSizeX,
    b.penetrationSizeY = edge.penetrationSizeY,
    b.penetrationSizeZ = edge.penetrationSizeZ

// SENSOR2GRAPH Cypher queries
-- name: RETRIEVE_WALL_ATTRIBUTES
MATCH (w:Wall {id: $element_id})
RETURN w.id AS id, w.name AS name, w.ifcClass AS ifcClass, w.layerCount AS layerCount
