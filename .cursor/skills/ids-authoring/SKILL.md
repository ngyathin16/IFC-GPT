---
name: ids-authoring
description: >
  Writing and maintaining IDS (Information Delivery Specification) XML files.
  Use when creating or modifying ids/*.ids files or working with IfcTester.
---

## IDS Structure
- XML namespace: `http://standards.buildingsmart.org/IDS`
- Schema: `http://standards.buildingsmart.org/IDS/1.0/ids.xsd`
- Two sections: `<info>` (metadata) and `<specifications>` (requirements)

## Specification Pattern
Each `<specification>` has:
- `<applicability>`: which IFC entities this applies to
- `<requirements>`: what those entities must satisfy
- Facet types: `<entity>`, `<property>`, `<partOf>`, `<attribute>`, `<classification>`, `<material>`

## Common Patterns Used in v0.ids

### Entity existence check (applicability only, no requirements)
```xml
<specification name="IfcProject must exist" ifcVersion="IFC4" minOccurs="1">
  <applicability>
    <entity><name><simpleValue>IFCPROJECT</simpleValue></name></entity>
  </applicability>
</specification>
```

### Property check
```xml
<specification name="Walls require IsExternal" ifcVersion="IFC4" minOccurs="1">
  <applicability>
    <entity><name><simpleValue>IFCWALL</simpleValue></name></entity>
  </applicability>
  <requirements>
    <property datatype="IFCBOOLEAN">
      <propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet>
      <baseName><simpleValue>IsExternal</simpleValue></baseName>
    </property>
  </requirements>
</specification>
```

### Spatial containment check
```xml
<specification name="Walls must be in IfcBuildingStorey" ifcVersion="IFC4" minOccurs="1">
  <applicability>
    <entity><name><simpleValue>IFCWALL</simpleValue></name></entity>
  </applicability>
  <requirements>
    <partOf relation="IFCRELCONTAINEDINSPATIALSTRUCTURE">
      <entity><name><simpleValue>IFCBUILDINGSTOREY</simpleValue></name></entity>
    </partOf>
  </requirements>
</specification>
```

## Our v0.ids: 13 Specifications
| # | Name | Entity | Check |
|---|------|--------|-------|
| 1 | IfcProject exists | IfcProject | existence |
| 2 | IfcSite exists | IfcSite | existence |
| 3 | IfcBuilding exists | IfcBuilding | existence |
| 4 | IfcBuildingStorey exists | IfcBuildingStorey | existence |
| 5 | Wall IsExternal | IfcWall | Pset_WallCommon.IsExternal |
| 6 | Wall in storey | IfcWall | partOf IfcBuildingStorey |
| 7 | Slab IsExternal | IfcSlab | Pset_SlabCommon.IsExternal |
| 8 | Slab in storey | IfcSlab | partOf IfcBuildingStorey |
| 9 | Door IsExternal | IfcDoor | Pset_DoorCommon.IsExternal |
| 10 | Door in storey | IfcDoor | partOf IfcBuildingStorey |
| 11 | Window IsExternal | IfcWindow | Pset_WindowCommon.IsExternal |
| 12 | Window in storey | IfcWindow | partOf IfcBuildingStorey |
| 13 | Roof in storey | IfcRoof | partOf IfcBuildingStorey |

## Testing IDS Files
```bash
# HTML report
python -m ifctester ids/v0.ids output.ifc -r Html -o reports/ids_latest.html

# JSON report (machine-readable, used by repair node)
python -m ifctester ids/v0.ids output.ifc -r Json -o reports/ids_latest.json

# Programmatic (in validate/ids_validate.py)
from ifctester import ids, reporter
my_ids = ids.open("ids/v0.ids")
my_ids.validate(ifcopenshell.open("output.ifc"))
```

## Key Files
- `ids/v0.ids` — The current IDS specification file
- `.cursor/skills/ids-authoring/ids-v0-annotated.xml` — Annotated reference copy
