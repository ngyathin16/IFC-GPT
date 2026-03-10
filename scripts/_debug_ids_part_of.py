"""Debug: Inspect how ifctester handles the partOf IFCRELVOIDSELEMENT IFCRELFILLSELEMENT relation."""
import inspect
from ifctester import facet as facet_module

# Find the partOf facet class
src = inspect.getsource(facet_module)
# Print the part that handles partOf / relations
idx = src.find("class PartOf")
print(src[idx: idx + 3000] if idx != -1 else "PartOf class not found")
