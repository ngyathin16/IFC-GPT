"""Debug: Inspect full PartOf.__call__ logic for combined relation."""
import inspect
from ifctester import facet as facet_module

src = inspect.getsource(facet_module)
idx = src.find("class PartOf")
# Print up to 6000 chars to capture the full __call__
print(src[idx: idx + 6000])
