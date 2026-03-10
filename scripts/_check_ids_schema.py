"""Print the valid 'relations' enum values from the installed ifctester IDS XSD."""
import ifctester
import os
import re

xsd_path = os.path.join(os.path.dirname(ifctester.__file__), "ids.xsd")
data = open(xsd_path, encoding="utf-8").read()

# Find the relations simpleType block
matches = list(re.finditer(r'simpleType[^>]*name=["\']relations["\']', data))
for m in matches:
    block = data[m.start(): m.start() + 1200]
    print(block)
    print("---")

# Also print the full XSD error context — just grep enumeration values
print("\nAll enumeration values in IDS XSD:")
for ev in re.findall(r'<xs:enumeration\s+value="([^"]+)"', data):
    print(" ", ev)
