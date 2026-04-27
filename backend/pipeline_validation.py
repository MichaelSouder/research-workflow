"""Validate pipeline definition (nodes, edges): allowed types and DAG."""

# Allowed types = component registry (qualtrics, process, grid, box) + legacy/planned types.
# Registry components are run by the generic runner; others are allowed for graph validation only.
def _allowed_node_types() -> frozenset[str]:
    try:
        from backend.pipeline.components import allowed_node_types as registry_types
        reg = registry_types()
    except Exception:
        reg = frozenset()
    legacy = frozenset({
        "file_import",
        "normalize",
        "duplicate_skip",
        "fraud",
        "webhook",
        "http_call",
        "stage",
    })
    return reg | legacy


ALLOWED_NODE_TYPES = _allowed_node_types()


def _custom_component_type_ids() -> frozenset[str]:
    """Return registered custom component ids (source='custom')."""
    try:
        from backend.pipeline.components import list_components

        return frozenset(
            m.id for m in list_components() if getattr(m, "source", "") == "custom"
        )
    except Exception:
        return frozenset()


def _resolve_effective_type(node_id: str, node_type: str) -> str:
    """
    Resolve effective node type for validation rules.
    Legacy/default graphs may store type='stage' and encode actual component in node id.
    """
    if node_type == "stage" and node_id in ALLOWED_NODE_TYPES:
        return node_id
    return node_type


def validate_pipeline(nodes: list, edges: list) -> list[str]:
    """
    Validate nodes and edges. Returns list of node ids in topological order.
    Raises ValueError if invalid (unknown type, cycle, missing node refs).
    """
    if not nodes:
        raise ValueError("Pipeline must have at least one node")
    node_ids = set()
    node_types = {}
    for n in nodes:
        if not isinstance(n, dict):
            raise ValueError("Each node must be an object")
        nid = n.get("id")
        if not nid or not isinstance(nid, str):
            raise ValueError("Each node must have a string id")
        if nid in node_ids:
            raise ValueError(f"Duplicate node id: {nid}")
        node_ids.add(nid)
        typ = n.get("type", "stage")
        if not isinstance(typ, str):
            typ = "stage"
        if typ not in ALLOWED_NODE_TYPES:
            raise ValueError(f"Unknown node type: {typ!r}. Allowed: {sorted(ALLOWED_NODE_TYPES)}")
        node_types[nid] = _resolve_effective_type(nid, typ)

    for e in edges:
        if not isinstance(e, dict):
            raise ValueError("Each edge must be an object")
        src = e.get("source")
        tgt = e.get("target")
        if src not in node_ids or tgt not in node_ids:
            raise ValueError(f"Edge references missing node: {src} -> {tgt}")

    # Topological sort (Kahn) to detect cycle and get order
    in_degree = {nid: 0 for nid in node_ids}
    out_edges = {nid: [] for nid in node_ids}
    for e in edges:
        src, tgt = e.get("source"), e.get("target")
        if src in node_ids and tgt in node_ids:
            out_edges[src].append(tgt)
            in_degree[tgt] = in_degree.get(tgt, 0) + 1

    queue = [nid for nid in node_ids if in_degree[nid] == 0]
    order = []
    while queue:
        nid = queue.pop(0)
        order.append(nid)
        for tgt in out_edges[nid]:
            in_degree[tgt] -= 1
            if in_degree[tgt] == 0:
                queue.append(tgt)

    if len(order) != len(node_ids):
        raise ValueError("Pipeline graph has a cycle")

    # Security rule: custom components cannot be terminal sink nodes (final data residence).
    custom_ids = _custom_component_type_ids()
    if custom_ids:
        sink_nodes = [nid for nid, targets in out_edges.items() if not targets]
        bad_sinks = [
            nid for nid in sink_nodes if node_types.get(nid) in custom_ids
        ]
        if bad_sinks:
            raise ValueError(
                "Custom components cannot be terminal sink nodes. "
                f"Add a built-in sink after: {sorted(bad_sinks)}"
            )
    return order
