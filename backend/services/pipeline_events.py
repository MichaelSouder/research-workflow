"""
In-memory pub/sub for pipeline definition events (create/update/delete).
Used by the SSE stream endpoint so clients can hot-reload when another tab or service changes a pipeline.
Single-process only; for multi-worker use Redis (Phase 3).
"""

import asyncio
import json
from typing import Any, AsyncIterator

# study_id -> list of queues; each queue gets all events for that study
_channels: dict[str, list[asyncio.Queue]] = {}
_lock = asyncio.Lock()


async def subscribe(
    study_id: str,
    pipeline_id: str | None = None,
) -> AsyncIterator[dict[str, Any]]:
    """
    Subscribe to pipeline events for a study. Yields event payloads (dict with event, pipelineId, studyId, ...).
    If pipeline_id is set, only yield events for that pipeline.
    When the iterator is closed, the subscription is removed.
    """
    queue: asyncio.Queue = asyncio.Queue()
    async with _lock:
        _channels.setdefault(study_id, []).append(queue)
    try:
        while True:
            try:
                payload = await queue.get()
            except asyncio.CancelledError:
                break
            if pipeline_id is not None and payload.get("pipelineId") != pipeline_id:
                continue
            yield payload
    finally:
        async with _lock:
            lst = _channels.get(study_id, [])
            if queue in lst:
                lst.remove(queue)
            if not lst:
                _channels.pop(study_id, None)


def publish(
    study_id: str,
    pipeline_id: str,
    event: str,
    payload: dict[str, Any],
) -> None:
    """
    Publish an event to all subscribers for this study. Call from request handlers (sync).
    payload should include at least: event, pipelineId, studyId; for updated/created include name, nodes, edges.
    """
    full = {"event": event, "pipelineId": pipeline_id, "studyId": study_id, **payload}
    # Schedule put on the event loop so we don't block the request
    queues = _channels.get(study_id, [])[:]
    for q in queues:
        try:
            q.put_nowait(full)
        except asyncio.QueueFull:
            pass
