# MEP Geometry Representations in IFC

**File analysed:** `ifc_models/test/test_MEP.ifc` (IFC2X3 schema)

---

## Summary

Not all MEP elements share the same geometry representation. The file contains three distinct geometry types depending on element discipline and role:

| Element | IFC class | Count | Geometry | shapeType |
|---|---|---|---|---|
| Pipe segments | `IfcFlowSegment` | 22 | `IfcExtrudedAreaSolid` (direct) | cylindrical |
| Pipe fittings (elbows, tees) | `IfcFlowFitting` | 12 | `IfcMappedItem` → `IfcFacetedBrep` | other |
| Electrical terminals (outlets, switches, panelboard) | `IfcBuildingElementProxy` | 8 | `IfcMappedItem` → `IfcExtrudedAreaSolid` ×N | rectangular |

Three named systems are present: `Domestic Cold Water 1`, `Domestic Hot Water 2`, and an unnamed electrical system (`'1'`). No cable or conduit routing is modelled.

---

## Plumbing — Pipe Segments (`IfcExtrudedAreaSolid`)

Straight pipe segments have a constant circular cross-section extruded along a linear axis. This maps directly to `IfcExtrudedAreaSolid`, which requires only:

- a profile definition (circle)
- an extrusion direction
- a depth value

This is a compact, parametric representation — no tessellation needed.

---

## Plumbing — Pipe Fittings (`IfcFacetedBrep` via `IfcMappedItem`)

Fittings (elbows, tees) have geometrically complex shapes that cannot be expressed as a simple extrusion:

- **Elbows** sweep a circular profile along a *curved* path, not a straight line.
- **Tees** branch into multiple directions — no single profile describes the full shape.

Rather than using higher-order swept solid types (e.g., `IfcFixedReferenceSweptAreaSolid`), the BIM authoring tool (Revit, evident from element names such as `Tee - Generic:Standard` and `Elbow - Generic:Standard`) pre-tessellates these shapes and exports them as `IfcFacetedBrep` — a triangulated mesh representation.

### Role of `IfcMappedItem`

`IfcMappedItem` is IFC's geometry instancing mechanism. All fittings of the same type share a *single* geometry definition in the file. Each instance is an `IfcMappedItem` containing only a transformation matrix that positions the shared geometry in space — analogous to a block insert in DWG/DXF. This avoids duplicating geometry for every instance.

---

## Electrical — `IfcBuildingElementProxy`

Electrical elements are not exported as typed IFC electrical classes. Instead, all 8 elements are `IfcBuildingElementProxy` — a generic catch-all:

| Element | Count |
|---|---|
| Duplex Receptacle (GFCI outlets) | 4 |
| Lighting Switches (Three Way) | 3 |
| Lighting & Appliance Panelboard (208V MLO) | 1 |

**Why `IfcBuildingElementProxy`?**  
IFC2X3 does define typed electrical classes (`IfcOutlet`, `IfcElectricAppliance`, `IfcLightFixture`), but Revit's IFC exporter historically fails to map its electrical families to those types and falls back to `IfcBuildingElementProxy`. The semantic identity of an element (outlet vs. switch) is only recoverable from the name string.

**Geometry:** all electrical proxies use `IfcMappedItem` → `IfcExtrudedAreaSolid`. Outlets and switches are box-shaped — rectangular extrusions — so their geometry *can* be expressed parametrically, unlike the curved pipe fittings.

**Multi-solid caveat:** each electrical proxy is built from **more than one** `IfcExtrudedAreaSolid` — typically a device **body** plus a thin **faceplate**. For example a Duplex Receptacle contains:

| Solid | XDim × YDim × Depth (mm) | Role |
|---|---|---|
| body | 38.1 × 76.2 × **53.98** | the device volume of interest |
| faceplate | 69.85 × 114.3 × **4.76** | cosmetic cover plate |

The shallow faceplate is not of interest. The pipeline therefore treats the **deepest** extrusion as the representative solid and discards the rest (see Processing below). The mapping transforms (`MappingOrigin`, `MappingTarget`) are identity in these Revit exports, so the mapped geometry needs only the element's `ObjectPlacement` to reach world coordinates.

**What is missing:** no cable, wire, or conduit routing is modelled. Only the physical terminal devices appear. In Revit, electrical wiring lives in a separate, non-geometric system and is not exported to IFC.

---

## How the Pipeline Represents MEP Geometry

Each element is classified into a `shapeType` and represented **by its swept solid** wherever one exists, falling back to a bounding box only when it does not. The mechanism is **shape-type dependent**:

| shapeType | Source geometry | Representation stored | Center |
|---|---|---|---|
| `cylindrical` | circular `IfcExtrudedAreaSolid` | finite cylinder: `center`, `direction`, `radius`, `length` | parametric solid center |
| `rectangular` | rectangular `IfcExtrudedAreaSolid` (deepest solid) | oriented box: `center`, `direction`, `axisX`, `sizeX/Y/Z` | parametric solid center |
| `other` | `IfcFacetedBrep` (fittings) | axis-aligned bounding box: `bbox_min`, `bbox_max` | mesh centroid |

Key points of the mechanism:

- **Deepest-solid selection.** When an element has several extrusions (the electrical body + faceplate), the one with the greatest `Depth` is chosen as the representative solid; shallower companions are dropped. This flows through classification, dimensions, direction, and center consistently.
- **Parametric, not tessellated.** Center and extents for cyl/rect are computed directly from IFC attributes (profile + depth + placement), so a dropped faceplate never skews them. Reconstruction of a pipe's bounding box from its cylinder matches the tessellated box to ~0.1 mm.
- **`direction`** — world-space extrusion axis (unit vector), the run direction of a pipe / depth axis of a device. `None` for fittings (no extrusion).
- **`axisX`** — world-space in-plane X axis of a rectangular box, needed to fix the box's rotation about its extrusion axis (a cylinder is rotationally symmetric and needs none). The third axis is derived as `direction × axisX`.
- **On-demand AABB.** Spatial relationship checks (MEP↔wall penetration, MEP↔space containment) no longer read a stored bbox for cyl/rect; they reconstruct the axis-aligned bounding box from the swept solid at query time. `other` elements still use their stored bbox.

### Graph encoding

`MEPElement` nodes are encoded shape-type dependently, mirroring the table above:

- **cylindrical / rectangular** — store the swept-solid parameters (`center`, `direction`, `radius`/`length` or `axisX`/`sizeX`/`sizeY`/`sizeZ`); **`bbox` is not encoded** (it is redundant and reconstructable).
- **other** — store `bbox_min`/`bbox_max` as the only geometric descriptor.

---

## Design Rationale

The geometry choices are not arbitrary — they reflect well-established IFC export conventions:

- **Simple prismatic shapes** → parametric (`IfcExtrudedAreaSolid`)
- **Complex or curved shapes** → baked tessellation (`IfcFacetedBrep`), instanced via `IfcMappedItem`
- **Electrical terminals** → `IfcBuildingElementProxy` due to Revit's exporter not mapping to typed electrical IFC classes

This pattern is standard behaviour in Revit's IFC exporter and is common across real-world IFC models.
