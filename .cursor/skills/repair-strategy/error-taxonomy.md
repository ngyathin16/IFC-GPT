# Error Taxonomy — Full Classification Table

## Category Definitions

| Category | Code | Source Validator | Severity | Auto-Repairable |
|----------|------|-----------------|----------|-----------------|
| `missing_pset` | E01 | IDS | ERROR | ✅ Always |
| `no_spatial_container` | E02 | IDS / Semantic | ERROR | ✅ Always |
| `floating_opening` | E03 | Semantic | WARNING | ✅ Usually |
| `schema_error` | E04 | Schema | ERROR | ⚠️ Sometimes |
| `missing_entity` | E05 | IDS | ERROR | ✅ Usually |
| `zero_thickness` | E06 | Semantic | ERROR | ✅ Always |
| `overlapping_walls` | E07 | Semantic | WARNING | ⚠️ Complex |
| `invalid_hierarchy` | E08 | Schema | ERROR | ❌ Regenerate |
| `missing_representation` | E09 | Schema | ERROR | ⚠️ Sometimes |
| `invalid_placement` | E10 | Schema | ERROR | ⚠️ Sometimes |

---

## Category Detail

### E01 — `missing_pset`
**Description:** An element is missing a required property set (e.g., `Pset_WallCommon.IsExternal`).  
**Source:** IDS specification failure  
**Repair:** Add pset and set property value via `execute_ifc_code_tool`  
**Template:**
```python
element = ifc.by_guid('<GUID>')
pset = ifcopenshell.api.run('pset.add_pset', ifc, product=element, name='<PsetName>')
ifcopenshell.api.run('pset.edit_pset', ifc, pset=pset, properties={'<PropName>': <Value>})
save_and_load_ifc()
```

### E02 — `no_spatial_container`
**Description:** An element is not assigned to any `IfcBuildingStorey`.  
**Source:** IDS partOf check / semantic orphan check  
**Repair:** Assign to the correct storey via `execute_ifc_code_tool`  
**Template:**
```python
element = ifc.by_guid('<GUID>')
storey = next(s for s in ifc.by_type('IfcBuildingStorey') if s.Name == '<StoreyName>')
ifcopenshell.api.run('spatial.assign_container', ifc, products=[element], relating_structure=storey)
save_and_load_ifc()
```

### E03 — `floating_opening`
**Description:** A door or window exists but has no `FillsVoids` relationship (not filling any opening in a wall).  
**Source:** Semantic check  
**Severity:** WARNING (non-blocking for export)  
**Repair:** Reposition opening to nearest wall using `update_door` / `update_window`  
**Note:** In v0, doors/windows are not required to fill voids — this is a warning only.

### E04 — `schema_error`
**Description:** IFC schema violation (e.g., wrong attribute type, missing required attribute).  
**Source:** `ifcopenshell.validate`  
**Repair:** Fix the specific attribute; parse error message for attribute name  
**Example error:** `IfcWall.Name must be STRING not None`  
**Template:** Use `attribute.edit_attributes` via `execute_ifc_code_tool`

### E05 — `missing_entity`
**Description:** IDS requires at least one entity of a type, but none exists (e.g., no `IfcProject`).  
**Source:** IDS minOccurs check  
**Repair:** Create the missing entity using `execute_ifc_code_tool` with proper spatial hierarchy  
**Note:** Spatial hierarchy gaps (no IfcBuilding when IfcBuildingStorey exists) are regenerate-level failures.

### E06 — `zero_thickness`
**Description:** A wall has `thickness <= 0` or below minimum (0.08m).  
**Source:** Semantic check  
**Repair:** `update_wall` with `dimensions={"thickness": 0.2}`  
**Always safe:** Minimum thickness of 0.2m (exterior) or 0.1m (interior) is correct.

### E07 — `overlapping_walls`
**Description:** Two wall bounding boxes overlap beyond the expected corner-join tolerance.  
**Source:** Semantic check  
**Repair:** Adjust endpoint coordinates to eliminate overlap  
**Complexity:** High — requires computing intersection and adjusting both walls  
**Threshold:** Overlap volume > 0.01m³ is flagged.

### E08 — `invalid_hierarchy`
**Description:** Spatial hierarchy is structurally broken (e.g., IfcBuildingStorey not contained in IfcBuilding).  
**Source:** Schema validation  
**Repair:** Cannot patch — requires full regeneration  
**Action:** Set `repair_attempts = 3` to force export, log regeneration needed.

### E09 — `missing_representation`
**Description:** An element exists in the IFC model but has no geometric representation (no body shape).  
**Source:** Schema validation  
**Repair:** Sometimes fixable by re-executing the create tool for that element  
**Caution:** Deleting + recreating breaks GUIDs — use update tools where possible.

### E10 — `invalid_placement`
**Description:** An element's local placement matrix is degenerate or invalid.  
**Source:** Schema validation  
**Repair:** Recalculate placement matrix using `execute_ifc_code_tool`  
**Template:** Use `ifcopenshell.api.run('geometry.edit_object_placement', ...)`.

---

## Repair Priority Order

When multiple errors exist, repair in this order to minimize cascading failures:
1. E08 `invalid_hierarchy` — detect early, escalate to regenerate
2. E02 `no_spatial_container` — fix containment before property checks
3. E01 `missing_pset` — most common, always safe
4. E05 `missing_entity` — create before referencing
5. E06 `zero_thickness` — geometry before semantic
6. E04 `schema_error` — attribute fixes
7. E09 `missing_representation` — geometry last (most disruptive)
8. E10 `invalid_placement` — placement last
9. E03 `floating_opening` — warning, lowest priority
10. E07 `overlapping_walls` — complex, attempt last or skip

---

## Error Classification Signal Patterns

Used in `classify_error(error: dict) -> str`:

```python
CATEGORY_PATTERNS = {
    "missing_pset":           ["Pset_", "property set", "IsExternal", "pset"],
    "no_spatial_container":   ["spatial container", "IfcBuildingStorey", "partOf", "containedIn"],
    "floating_opening":       ["FillsVoids", "filling", "opening"],
    "schema_error":           ["schema", "attribute", "type mismatch", "required"],
    "missing_entity":         ["minOccurs", "must exist", "no instance"],
    "zero_thickness":         ["thickness", "zero", "below minimum"],
    "overlapping_walls":      ["overlap", "intersection", "bounding box"],
    "invalid_hierarchy":      ["hierarchy", "IfcBuilding not found", "project structure"],
    "missing_representation": ["representation", "geometry", "shape"],
    "invalid_placement":      ["placement", "matrix", "degenerate"],
}
```
