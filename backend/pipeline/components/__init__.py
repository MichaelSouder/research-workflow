"""
Pipeline component registry: list manifests and get runner for each component id.
Built-in components are registered from code; custom components are loaded from backend/custom_components/*.json
by default (or CUSTOM_COMPONENTS_DIR/*.json when configured).
"""

from backend.pipeline.components.base import ComponentManifest, RunContext

# Registry: component_id -> (manifest, run_callable)
_registry: dict[str, tuple[ComponentManifest, object]] = {}


def _register(manifest: ComponentManifest, run_fn: object) -> None:
    _registry[manifest.id] = (manifest, run_fn)


def _load_builtins() -> None:
    from backend.pipeline.components import box, grid, process, qualtrics

    _register(qualtrics.MANIFEST, qualtrics.run)
    _register(process.MANIFEST, process.run)
    _register(grid.MANIFEST, grid.run)
    _register(box.MANIFEST, box.run)


def _load_custom() -> None:
    from backend.pipeline.components.custom_store import load_custom_component, list_custom_component_ids
    from backend.pipeline.components.sandbox import run_custom_component

    for cid in list_custom_component_ids():
        if cid in _registry:
            continue
        loaded = load_custom_component(cid)
        if not loaded:
            continue
        manifest, code = loaded

        def _make_runner(c: str):
            def runner(inputs: dict, config: dict, context: RunContext) -> dict:
                return run_custom_component(c, inputs, config, context)

            return runner

        _register(manifest, _make_runner(code))


def _ensure_loaded() -> None:
    if _registry:
        return
    _load_builtins()
    _load_custom()


def list_components() -> list[ComponentManifest]:
    """Return all registered component manifests (built-in + custom)."""
    _ensure_loaded()
    return [m for m, _ in _registry.values()]


def get_manifest(component_id: str) -> ComponentManifest | None:
    """Return manifest for component_id or None if not found."""
    _ensure_loaded()
    entry = _registry.get(component_id)
    return entry[0] if entry else None


def get_runner(component_id: str):
    """
    Return the run(inputs, config, context) callable for component_id.
    Raises KeyError if component_id is not registered.
    """
    _ensure_loaded()
    entry = _registry.get(component_id)
    if not entry:
        raise KeyError(f"Unknown component: {component_id!r}")
    return entry[1]


def has_component(component_id: str) -> bool:
    """Return True if component_id is registered."""
    _ensure_loaded()
    return component_id in _registry


def allowed_node_types() -> frozenset[str]:
    """Return the set of component ids that are valid node types (for validation)."""
    _ensure_loaded()
    return frozenset(_registry.keys())


def reload_custom_components() -> None:
    """Clear registry and reload (built-ins + custom). Call after creating/updating/deleting custom components."""
    _registry.clear()
    _ensure_loaded()


__all__ = [
    "list_components",
    "get_manifest",
    "get_runner",
    "has_component",
    "allowed_node_types",
    "RunContext",
]
