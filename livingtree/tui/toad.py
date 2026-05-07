"""Shim: allow 'import toad' to resolve to the vendored td/ framework."""
import importlib
import os as _os
import sys as _sys

# Ensure the parent directory is importable
_parent = _os.path.dirname(_os.path.abspath(__file__))
if _parent not in _sys.path:
    _sys.path.insert(0, _parent)

_td = importlib.import_module("td")
_sys.modules["toad"] = _td
# Re-export all names
for _attr in dir(_td):
    if not _attr.startswith("_"):
        globals()[_attr] = getattr(_td, _attr)
