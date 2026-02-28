"""
Scanner registry with auto-discovery.

Drop a new scanner file in this package, subclass BaseScanner with the required
class-level metadata, and the registry picks it up automatically — no edits
needed in tools.py, scorer.py, or the frontend.
"""
import importlib
import inspect
import pkgutil

from scanners.base import BaseScanner

_REGISTRY: dict[str, type[BaseScanner]] = {}

for _info in pkgutil.iter_modules(__path__):
    if _info.name == "base":
        continue
    _mod = importlib.import_module(f"{__name__}.{_info.name}")
    for _, _cls in inspect.getmembers(_mod, inspect.isclass):
        if issubclass(_cls, BaseScanner) and _cls is not BaseScanner and _cls.name:
            _REGISTRY[_cls.name] = _cls


def get_scanners(tier: str = "deep") -> list[type[BaseScanner]]:
    """Return scanner classes for the given tier ('quick' or 'deep')."""
    if tier == "deep":
        return list(_REGISTRY.values())
    return [cls for cls in _REGISTRY.values() if cls.tier == "quick"]


def get_registry() -> dict[str, type[BaseScanner]]:
    """Return the full name -> class mapping."""
    return dict(_REGISTRY)


def get_source_labels() -> list[str]:
    """Human-friendly labels for all registered scanners."""
    return [cls.display_label or cls.name for cls in _REGISTRY.values()]
