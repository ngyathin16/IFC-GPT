# IDS Format Guide — v0.ids Specification Patterns

## IDS XML Skeleton
```xml
<?xml version="1.0" encoding="UTF-8"?>
<ids xmlns="http://standards.buildingsmart.org/IDS"
     xmlns:xs="http://www.w3.org/2001/XMLSchema"
     xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
     xsi:schemaLocation="http://standards.buildingsmart.org/IDS
         http://standards.buildingsmart.org/IDS/1.0/ids.xsd">
  <info>
    <title>IFC-GPT v0 Validation Requirements</title>
    <version>0.1</version>
    <description>Baseline IDS for LLM-generated IFC4 buildings</description>
  </info>
  <specifications>
    <!-- specifications here -->
  </specifications>
</ids>
```

## Facet Types Reference

### `<entity>` — Filter by IFC class
```xml
<entity>
  <name><simpleValue>IFCWALL</simpleValue></name>
  <!-- optional: <predefinedType><simpleValue>SOLIDWALL</simpleValue></predefinedType> -->
</entity>
```

### `<property>` — Require a property set value
```xml
<property datatype="IFCBOOLEAN">
  <propertySet><simpleValue>Pset_WallCommon</simpleValue></propertySet>
  <baseName><simpleValue>IsExternal</simpleValue></baseName>
  <!-- optional: <value><simpleValue>TRUE</simpleValue></value> -->
</property>
```

### `<partOf>` — Require spatial containment
```xml
<partOf relation="IFCRELCONTAINEDINSPATIALSTRUCTURE">
  <entity>
    <name><simpleValue>IFCBUILDINGSTOREY</simpleValue></name>
  </entity>
</partOf>
```

### `<attribute>` — Require an IFC attribute value
```xml
<attribute>
  <name><simpleValue>Name</simpleValue></name>
  <value><simpleValue>Ground Floor</simpleValue></value>
</attribute>
```

## minOccurs / maxOccurs
- `minOccurs="1"` — at least one matching element must exist (default)
- `minOccurs="0"` — optional check (only validates if element exists)
- `maxOccurs="unbounded"` — no upper limit (default)

## Cardinality on applicability vs requirements
- `<applicability>` selects elements to check
- `<requirements>` defines what those elements must have
- A specification PASSES if ALL selected elements satisfy ALL requirements

## v0.ids — Our 13 Specifications

```
Spec 1:  IfcProject must exist (minOccurs=1)
Spec 2:  IfcSite must exist (minOccurs=1)
Spec 3:  IfcBuilding must exist (minOccurs=1)
Spec 4:  IfcBuildingStorey must exist (minOccurs=1)
Spec 5:  IfcWall → Pset_WallCommon.IsExternal (IFCBOOLEAN)
Spec 6:  IfcWall → partOf IfcBuildingStorey
Spec 7:  IfcSlab → Pset_SlabCommon.IsExternal (IFCBOOLEAN)
Spec 8:  IfcSlab → partOf IfcBuildingStorey
Spec 9:  IfcDoor → Pset_DoorCommon.IsExternal (IFCBOOLEAN)
Spec 10: IfcDoor → partOf IfcBuildingStorey
Spec 11: IfcWindow → Pset_WindowCommon.IsExternal (IFCBOOLEAN)
Spec 12: IfcWindow → partOf IfcBuildingStorey
Spec 13: IfcRoof → partOf IfcBuildingStorey
```

## Running IfcTester Programmatically (in ids_validate.py)
```python
import ifcopenshell
from ifctester import ids, reporter

def run_ids_validation(ifc_path: str, ids_path: str) -> dict:
    model = ifcopenshell.open(ifc_path)
    my_ids = ids.open(ids_path)
    my_ids.validate(model)
    r = reporter.Json(my_ids)
    r.report()
    return r.to_string()  # JSON string
```
