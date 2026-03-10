"""Debug: Print the IFCRELVOIDSELEMENT IFCRELFILLSELEMENT branch of PartOf.__call__."""
import inspect
from ifctester import facet as facet_module

src = inspect.getsource(facet_module)
idx = src.find("IFCRELVOIDSELEMENT")
print(src[idx: idx + 1500] if idx != -1 else "NOT FOUND")
