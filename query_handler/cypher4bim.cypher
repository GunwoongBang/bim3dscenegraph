-- name: RESET_DATABASE
MATCH (n)
DETACH DELETE n

-- name: ENSURE_SCHEMA_SPACES
CREATE CONSTRAINT space_id IF NOT EXISTS FOR (s:Space) REQUIRE s.id IS UNIQUE

-- name: ENSURE_SCHEMA_WALLS
CREATE CONSTRAINT wall_id IF NOT EXISTS FOR (w:Wall) REQUIRE w.id IS UNIQUE

-- name: ENSURE_SCHEMA_LAYERS
CREATE CONSTRAINT layer_id IF NOT EXISTS FOR (l:Layer) REQUIRE l.id IS UNIQUE

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
    w.bbox_min = wall.bbox_min,
    w.bbox_max = wall.bbox_max,
    w.directionSense = wall.directionSense,
    w.layerCount = wall.layerCount,
    w.axis2 = wall.axis2,
    w.center = wall.center

-- name: UPSERT_LAYERS
UNWIND $layers AS layer
MERGE (l:Layer { id: layer.id })
SET l.name = layer.name,
    l.ifcClass = layer.ifcClass,
    l.layerIndex = layer.layerIndex,
    l.thickness = layer.thickness

-- name: CREATE_WALL_LAYER_EDGES
UNWIND $layers AS layer
MATCH (w:Wall { id: layer.wall_id })
MATCH (l:Layer { id: layer.id })
MERGE (w)-[:HAS_LAYER]->(l)

-- name: CREATE_SPACE_WALL_EDGES
UNWIND $edges AS edge
MATCH (s:Space { id: edge.space_id })
MATCH (w:Wall { id: edge.wall_id })
MERGE (s)-[r:BOUNDED_BY]->(w)
SET r.side = edge.side,
    r.boundaryType = edge.boundaryType

-- name: GET_LAYERS_FROM_SPACE
// Get wall layers in order as seen FROM a specific space
// Usage: CALL this with spaceName parameter
MATCH (s:Space {name: $spaceName})-[b:BOUNDED_BY]->(w:Wall)-[:HAS_LAYER]->(l:Layer)
WITH s, w, b, l,
     CASE 
       WHEN b.side = w.directionSense THEN w.layerCount - l.layerIndex - 1
       ELSE l.layerIndex
     END AS viewOrder
RETURN s.name AS space, 
       w.name AS wall,
       l.name AS material, 
       l.thickness AS thickness,
       viewOrder AS orderFromSpace
ORDER BY w.name, viewOrder

-- name: GET_SURFACE_MATERIAL_FROM_SPACE
// Get the first layer (surface material) visible from each space
MATCH (s:Space)-[b:BOUNDED_BY]->(w:Wall)-[:HAS_LAYER]->(l:Layer)
WITH s, w, b, l,
     CASE 
       WHEN b.side = w.directionSense THEN w.layerCount - l.layerIndex - 1
       ELSE l.layerIndex
     END AS viewOrder
WHERE viewOrder = 0
RETURN s.name AS space, w.name AS wall, l.name AS surfaceMaterial

-- name: ENSURE_SCHEMA_MEP
CREATE CONSTRAINT mep_id IF NOT EXISTS FOR (m:MEP) REQUIRE m.id IS UNIQUE

-- name: UPSERT_MEP_ELEMENTS
UNWIND $elements AS elem
MERGE (m:MEP { id: elem.id })
SET m.name = elem.name,
    m.ifcClass = elem.ifcClass,
    m.objectType = elem.objectType,
    m.center = elem.center,
    m.bbox_min = elem.bbox_min,
    m.bbox_max = elem.bbox_max

-- name: CREATE_MEP_WALL_EDGES
UNWIND $edges AS edge
MATCH (m:MEP { id: edge.mep_id })
MATCH (w:Wall { id: edge.wall_id })
CALL (m, w, edge) {
  WITH m, w, edge
  WHERE edge.relationship = 'PASSES_THROUGH'
  MERGE (m)-[:PASSES_THROUGH]->(w)
  UNION
  WITH m, w, edge
  WHERE edge.relationship = 'NEAR'
  MERGE (m)-[:NEAR]->(w)
}

-- name: GET_MEP_NEAR_WALL
// Find MEP elements that pass through or are near a specific wall
MATCH (m:MEP)-[r:PASSES_THROUGH|NEAR]->(w:Wall {name: $wallName})
RETURN m.name AS mepElement, 
       m.objectType AS type,
       type(r) AS relationship,
       w.name AS wall
