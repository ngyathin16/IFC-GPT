"""Root conftest.py — ensures project root is on sys.path for all pytest runs."""
import sys
from pathlib import Path

# Add project root so `validate`, `agent`, `scripts` packages are importable
sys.path.insert(0, str(Path(__file__).resolve().parent))
