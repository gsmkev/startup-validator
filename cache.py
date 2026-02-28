"""
In-memory cache with TTL for scanner results and keyword extraction.

Key format: hash(keywords + depth + source).
TTL: 15 minutes.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any

_CACHE_TTL = 900  # 15 minutes
_cache: dict[str, tuple[Any, float]] = {}


def _make_key(prefix: str, *parts: Any) -> str:
    blob = json.dumps(parts, sort_keys=True, default=str)
    h = hashlib.sha256(blob.encode()).hexdigest()[:24]
    return f"{prefix}:{h}"


def get(key: str) -> Any | None:
    if key not in _cache:
        return None
    value, expires = _cache[key]
    if time.monotonic() > expires:
        del _cache[key]
        return None
    return value


def set_(key: str, value: Any) -> None:
    _cache[key] = (value, time.monotonic() + _CACHE_TTL)


def get_cached_scan(source: str, depth: str, keywords: list[str]) -> dict | None:
    """Return cached ScanResult dict if valid."""
    key = _make_key("scan", source, depth, sorted(keywords))
    return get(key)


def set_cached_scan(source: str, depth: str, keywords: list[str], data: dict) -> None:
    key = _make_key("scan", source, depth, sorted(keywords))
    set_(key, data)


def get_cached_keywords(idea: str) -> list[str] | None:
    key = _make_key("keywords", idea)
    return get(key)


def set_cached_keywords(idea: str, keywords: list[str]) -> None:
    key = _make_key("keywords", idea)
    set_(key, keywords)
