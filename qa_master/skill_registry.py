"""Discover and route QA Master's bundled professional guidance.

This module only selects instructional files.  It neither invokes an agent nor
executes a test, so callers must preserve the returned planning-only state.
"""
from __future__ import annotations

from importlib import resources
from pathlib import Path
from typing import Iterable

from .core import DIMENSIONS

_GUIDE_FILES = (
    "requirements-review.md",
    "functional-api.md",
    "structural-integration.md",
    "nonfunctional-compatibility.md",
    "security-recovery.md",
    "regression-evidence.md",
)
_VALID_RISKS = {"low", "medium", "high"}
_REQUIRED_FIELDS = {"id", "title", "dimensions", "intents", "risks", "artifacts"}


def bundled_skill_root():
    """Return the package-resource directory holding the canonical guides.

    ``Traversable`` is deliberately returned instead of assuming resources are
    ordinary filesystem files; installed zip-compatible packages can therefore
    still be inspected through the resource API.
    """
    return resources.files("qa_master").joinpath("skills", "professional")


def _values(value: object) -> tuple[str, ...]:
    if not isinstance(value, str):
        return ()
    return tuple(item.strip() for item in value.split(",") if item.strip())


def _metadata(text: str) -> dict[str, object] | None:
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    result: dict[str, object] = {}
    for line in lines[1:]:
        if line.strip() == "---":
            break
        if ":" not in line:
            return None
        key, value = line.split(":", 1)
        key, value = key.strip(), value.strip()
        if not key or not value or key in result:
            return None
        result[key] = _values(value) if key in {"dimensions", "intents", "risks", "artifacts"} else value
    else:
        return None
    return result


def _iter_files(root) -> Iterable[object]:
    try:
        return sorted(root.iterdir(), key=lambda item: item.name)
    except (FileNotFoundError, NotADirectoryError, AttributeError):
        return ()


def discover_skills(root=None, *, required_files: Iterable[str] = _GUIDE_FILES) -> dict:
    """Return only valid guides physically present under *root*.

    Invalid, unreadable and missing required guides are explicit gaps.  A
    caller may pass a temporary ``Path`` in tests; normal operation reads the
    installed package resource directory.
    """
    root = bundled_skill_root() if root is None else root
    files = {item.name: item for item in _iter_files(root) if getattr(item, "is_file", lambda: False)()}
    guides, gaps, seen_ids = [], [], set()
    for expected in required_files:
        if expected not in files:
            gaps.append({"code": "GUIDE_FILE_MISSING", "file": expected})
    for name, item in sorted(files.items()):
        if not name.endswith(".md"):
            continue
        try:
            parsed = _metadata(item.read_text(encoding="utf-8"))
        except (OSError, UnicodeError):
            gaps.append({"code": "GUIDE_FILE_UNREADABLE", "file": name})
            continue
        if not parsed or _REQUIRED_FIELDS - set(parsed):
            gaps.append({"code": "GUIDE_METADATA_INVALID", "file": name})
            continue
        invalid_dimensions = set(parsed["dimensions"]) - set(DIMENSIONS)
        invalid_risks = set(parsed["risks"]) - _VALID_RISKS
        if invalid_dimensions:
            gaps.append({"code": "GUIDE_DIMENSION_INVALID", "file": name, "dimensions": sorted(invalid_dimensions)})
            continue
        if invalid_risks or not parsed["intents"] or not parsed["artifacts"]:
            gaps.append({"code": "GUIDE_METADATA_INVALID", "file": name})
            continue
        if parsed["id"] in seen_ids:
            gaps.append({"code": "GUIDE_ID_DUPLICATE", "file": name, "id": parsed["id"]})
            continue
        seen_ids.add(parsed["id"])
        guides.append({**parsed, "file": name, "path": str(item)})
    return {"guides": guides, "gaps": gaps, "status": "DISCOVERED" if guides else "NO_GUIDES_AVAILABLE"}


def _requested(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        return (value,)
    return tuple(str(item) for item in value)


def select_skills(intent: str | Iterable[str] | None = None, dimensions: Iterable[str] | None = None,
                  risk: str | None = None, *, root=None) -> dict:
    """Select verified instructional artifacts for the requested planning work."""
    requested_intents = _requested(intent)
    requested_dimensions = _requested(dimensions)
    found = discover_skills(root)
    gaps = list(found["gaps"])
    unknown = sorted(set(requested_dimensions) - set(DIMENSIONS))
    if unknown:
        gaps.append({"code": "UNKNOWN_DIMENSION", "dimensions": unknown})
    if risk is not None and risk not in _VALID_RISKS:
        gaps.append({"code": "UNKNOWN_RISK", "risk": risk})
    selected = []
    for guide in found["guides"]:
        if requested_intents and not set(requested_intents).intersection(guide["intents"]):
            continue
        if requested_dimensions and not set(requested_dimensions).intersection(guide["dimensions"]):
            continue
        if risk and risk in _VALID_RISKS and risk not in guide["risks"]:
            continue
        selected.append(guide)
    if not selected and not unknown:
        gaps.append({"code": "NO_MATCHING_BUNDLED_GUIDE", "intent": list(requested_intents),
                     "dimensions": list(requested_dimensions), "risk": risk})
    return {
        "status": "PLANNING_ONLY",
        "execution": "NOT_EXECUTED",
        "requested": {"intent": list(requested_intents), "dimensions": list(requested_dimensions), "risk": risk},
        "selected": selected,
        "gaps": gaps,
    }
