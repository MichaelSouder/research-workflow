"""
File-based store for custom pipeline components.
Each component is a single JSON file: { "manifest": {...}, "code": "..." }.
Directory: backend/custom_components/ by default, or CUSTOM_COMPONENTS_DIR when set.
"""

import json
import logging
import os
import re
from pathlib import Path

from backend.pipeline.components.base import (
    ComponentManifest,
    InputPort,
    OutputPort,
    PORT_TYPE_ANY,
)

# Project root (one level above backend/)
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent

# Default to backend/custom_components so container mounts can persist them.
_DEFAULT_COMPONENTS_DIR = _PROJECT_ROOT / "backend" / "custom_components"

# Component id must be safe for filename: alphanumeric and underscore only
_ID_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")

# Built-in ids cannot be overwritten by custom components
BUILTIN_IDS = frozenset({"qualtrics", "process", "grid", "box"})
logger = logging.getLogger(__name__)


def _components_dir() -> Path:
    configured = (os.environ.get("CUSTOM_COMPONENTS_DIR") or "").strip()
    if configured:
        d = Path(configured).expanduser()
        if not d.is_absolute():
            d = _PROJECT_ROOT / d
    else:
        d = _DEFAULT_COMPONENTS_DIR
    d.mkdir(parents=True, exist_ok=True)
    return d


def _validate_component_id(component_id: str) -> None:
    if not component_id or not isinstance(component_id, str):
        raise ValueError("component_id must be a non-empty string")
    if not _ID_PATTERN.match(component_id):
        raise ValueError(
            "component_id must start with a letter and contain only letters, numbers, and underscores"
        )
    if component_id in BUILTIN_IDS:
        raise ValueError(f"Cannot override built-in component: {component_id!r}")


def _manifest_from_dict(data: dict) -> ComponentManifest:
    """Build ComponentManifest from JSON-friendly dict."""
    inputs = [
        InputPort(
            id=p["id"],
            label=p.get("label"),
            type=p.get("type", PORT_TYPE_ANY),
            required=p.get("required", True),
        )
        for p in (data.get("inputs") or [])
    ]
    outputs = [
        OutputPort(
            id=p["id"],
            label=p.get("label"),
            type=p.get("type", PORT_TYPE_ANY),
        )
        for p in (data.get("outputs") or [])
    ]
    return ComponentManifest(
        id=data["id"],
        label=data["label"],
        description=data.get("description", ""),
        category=data.get("category", "custom"),
        inputs=inputs,
        outputs=outputs,
        config_keys=list(data.get("config_keys") or []),
        source="custom",
        version=data.get("version"),
        handles_sensitive_data=bool(data.get("handles_sensitive_data", False)),
    )


def _manifest_to_dict(manifest: ComponentManifest) -> dict:
    """Serialize ComponentManifest to JSON-friendly dict."""
    return {
        "id": manifest.id,
        "label": manifest.label,
        "description": manifest.description,
        "category": manifest.category,
        "inputs": [
            {"id": p.id, "label": p.label, "type": p.type, "required": p.required}
            for p in manifest.inputs
        ],
        "outputs": [{"id": p.id, "label": p.label, "type": p.type} for p in manifest.outputs],
        "config_keys": manifest.config_keys,
        "version": manifest.version,
        "handles_sensitive_data": getattr(manifest, "handles_sensitive_data", False),
    }


def list_custom_component_ids() -> list[str]:
    """Return ids of all custom components (from filenames)."""
    d = _components_dir()
    out = []
    for f in d.iterdir():
        if f.suffix == ".json" and f.is_file():
            # Ignore unsafe filenames instead of crashing registry load.
            if _ID_PATTERN.match(f.stem):
                out.append(f.stem)
            else:
                logger.warning("Ignoring custom component file with invalid id: %s", f.name)
    return sorted(out)


def load_custom_component(component_id: str) -> tuple[ComponentManifest, str] | None:
    """Load custom component by id. Returns (manifest, code) or None if not found."""
    _validate_component_id(component_id)
    path = _components_dir() / f"{component_id}.json"
    if not path.is_file():
        return None
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
        manifest_data = data.get("manifest")
        code = data.get("code") or ""
        if not manifest_data or "id" not in manifest_data or "label" not in manifest_data:
            logger.warning("Invalid custom component manifest shape in %s", path.name)
            return None
        manifest = _manifest_from_dict(manifest_data)
        return (manifest, code)
    except json.JSONDecodeError as e:
        logger.warning("Invalid JSON in custom component %s: %s", path.name, e)
        return None
    except Exception as e:
        logger.warning("Failed loading custom component %s: %s", path.name, e)
        return None


def save_custom_component(
    component_id: str,
    manifest: ComponentManifest,
    code: str,
) -> None:
    """Create or overwrite a custom component file."""
    _validate_component_id(component_id)
    if manifest.id != component_id:
        raise ValueError(f"manifest.id {manifest.id!r} must match component_id {component_id!r}")
    path = _components_dir() / f"{component_id}.json"
    tmp_path = path.with_suffix(".json.tmp")
    payload = {"manifest": _manifest_to_dict(manifest), "code": code}
    # Atomic write: write temp file then rename into place.
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def delete_custom_component(component_id: str) -> bool:
    """Remove a custom component file. Returns True if deleted, False if not found."""
    _validate_component_id(component_id)
    path = _components_dir() / f"{component_id}.json"
    if not path.is_file():
        return False
    path.unlink()
    return True
