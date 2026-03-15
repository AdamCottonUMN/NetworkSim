from __future__ import annotations
import heapq
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING

from .request import Request, RequestStatus

if TYPE_CHECKING:
    from .architecture import Architecture
    from .metrics import Metrics


# ---------------------------------------------------------------------------
# Event definition
# ---------------------------------------------------------------------------

class EventType(Enum):
    REQUEST_ARRIVE      = "request_arrive"
    PROCESSING_START    = "processing_start"
    PROCESSING_COMPLETE = "processing_complete"
    REQUEST_FAILED      = "request_failed"
    REQUEST_TIMEOUT     = "request_timeout"
    NODE_DOWN           = "node_down"
    NODE_UP             = "node_up"


@dataclass
class Event:
    time: float
    event_type: EventType
    request: Optional[Request] = None
    node_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Simulation engine
# ---------------------------------------------------------------------------

class SimulationEngine:
    """
    Discrete-event simulation loop.

    Events are stored in a min-heap keyed by (time, counter) so that
    ties are broken by insertion order rather than by comparing Requests.

    Typical usage
    -------------
    engine = SimulationEngine(architecture, metrics)
    for event in arrival_events:
        engine.schedule(event.time, event.event_type, event.request, event.node_id)
    engine.run(until=60.0)
    """

    def __init__(self, architecture: "Architecture", metrics: "Metrics"):
        self.architecture = architecture
        self.metrics = metrics
        self.current_time: float = 0.0
        self._heap: List = []    # (time, counter, Event)
        self._counter: int = 0   # monotonically increasing tie-breaker

    # ---------------------------------------------------------------- scheduling

    def schedule(
        self,
        time: float,
        event_type: EventType,
        request: Optional[Request] = None,
        node_id: Optional[str] = None,
    ) -> None:
        event = Event(time=time, event_type=event_type, request=request, node_id=node_id)
        heapq.heappush(self._heap, (time, self._counter, event))
        self._counter += 1

    # ---------------------------------------------------------------- main loop

    def run(self, until: float) -> None:
        """Process all events up to and including `until` seconds."""
        while self._heap:
            time, _, event = heapq.heappop(self._heap)
            if time > until:
                break
            self.current_time = time
            self._dispatch(event)

    # ---------------------------------------------------------------- dispatch

    def _dispatch(self, event: Event) -> None:
        dispatch = {
            EventType.REQUEST_ARRIVE:      self._on_arrive,
            EventType.PROCESSING_START:    self._on_processing_start,
            EventType.PROCESSING_COMPLETE: self._on_processing_complete,
            EventType.REQUEST_FAILED:      self._on_failed,
            EventType.REQUEST_TIMEOUT:     self._on_timeout,
            EventType.NODE_DOWN:           self._on_node_down,
            EventType.NODE_UP:             self._on_node_up,
        }
        dispatch[event.event_type](event)

    # ---------------------------------------------------------------- handlers

    # ---------------------------------------------------------------- resolution

    def _resolve_request(self, req: Request, success: bool, fail_node_id: str = '') -> None:
        """
        Mark req as completed or failed and propagate to its parent if it is a
        child request created by a fan-out node.  Handles arbitrarily nested
        fan-outs recursively.
        """
        if req.parent_req is not None:
            # Child request — update child state, then notify parent
            parent = req.parent_req
            if success:
                req.status = RequestStatus.COMPLETED
                req.completed_at = self.current_time
                if parent.status not in (RequestStatus.FAILED, RequestStatus.COMPLETED):
                    parent.pending_children -= 1
                    if parent.pending_children == 0:
                        self._resolve_request(parent, success=True)
            else:
                req.status = RequestStatus.FAILED
                req.failed_at = self.current_time
                if parent.status not in (RequestStatus.FAILED, RequestStatus.COMPLETED):
                    self._resolve_request(parent, success=False, fail_node_id=fail_node_id)
        else:
            # Top-level request — record in metrics
            if success:
                req.status = RequestStatus.COMPLETED
                req.completed_at = self.current_time
                self.metrics.record_completion(self.current_time, req)
            else:
                req.status = RequestStatus.FAILED
                req.failed_at = self.current_time
                self.metrics.record_failure(self.current_time, fail_node_id, req)

    # ---------------------------------------------------------------- handlers

    def _on_arrive(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        req = event.request
        req.current_node = node.id
        req.path.append(node.id)

        if node.is_down:
            self._resolve_request(req, success=False, fail_node_id=node.id)
            return

        self.metrics.record_arrival(self.current_time, node.id, node.queue_size)

        if node.accept(req):
            # Slot was free — start processing immediately
            self.schedule(self.current_time, EventType.PROCESSING_START, req, node.id)
        else:
            req.status = RequestStatus.QUEUED
            req.queued_at = self.current_time
            self.metrics.record_queued(self.current_time, node.id, node.queue_size)
            if node.timeout is not None:
                self.schedule(self.current_time + node.timeout, EventType.REQUEST_TIMEOUT, req, node.id)

    def _on_processing_start(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        req = event.request

        req.status = RequestStatus.PROCESSING
        if req.queued_at is None:          # arrived directly to a free slot
            req.queued_at = self.current_time
        req.processing_started_at = self.current_time

        self.metrics.record_processing_start(self.current_time, node.id, node.utilization)

        if node.should_fail():
            self.schedule(self.current_time, EventType.REQUEST_FAILED, req, node.id)
            return

        finish_time = self.current_time + node.sample_processing_time(req.request_type)
        self.schedule(finish_time, EventType.PROCESSING_COMPLETE, req, node.id)

    def _on_processing_complete(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        req = event.request

        # Free the slot and promote the next queued request (if any)
        next_req = node.release()
        if next_req:
            self.schedule(self.current_time, EventType.PROCESSING_START, next_req, node.id)

        self.metrics.record_processing_complete(
            self.current_time, node.id, node.utilization, node.queue_size
        )

        # Cache hit — serve here, don't forward downstream
        if node.is_cache_hit():
            self._resolve_request(req, success=True)
            return

        # Fan-out: dispatch one child request per outgoing edge simultaneously.
        # The parent completes only when ALL children resolve (scatter-gather).
        nexts = self.architecture.edges.get(node.id, [])
        if node.fan_out and len(nexts) >= 2:
            req.pending_children = len(nexts)
            for next_id in nexts:
                child = Request(
                    request_type=req.request_type,
                    created_at=req.created_at,
                    parent_req=req,
                )
                link_lat = self.architecture.get_link_latency(node.id, next_id)
                self.schedule(self.current_time + link_lat, EventType.REQUEST_ARRIVE, child, next_id)
            return  # parent waits; children will call _resolve_request when done

        # Normal single-path routing
        next_node_id = self.architecture.get_next_node(node.id)
        if next_node_id:
            link_lat = self.architecture.get_link_latency(node.id, next_node_id)
            self.schedule(self.current_time + link_lat, EventType.REQUEST_ARRIVE, req, next_node_id)
        else:
            self._resolve_request(req, success=True)

    def _on_node_down(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        node.go_down()
        self.metrics.record_node_down(self.current_time, node.id)

    def _on_node_up(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        node.come_up()
        self.metrics.record_node_up(self.current_time, node.id)
        for req in node.drain_to_capacity():
            self.schedule(self.current_time, EventType.PROCESSING_START, req, node.id)

    def schedule_outage(self, node_id: str, start: float, duration: float) -> None:
        self.schedule(start,            EventType.NODE_DOWN, node_id=node_id)
        self.schedule(start + duration, EventType.NODE_UP,   node_id=node_id)

    def _on_timeout(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        req = event.request

        if req.status != RequestStatus.QUEUED:
            return

        if not node.remove_from_queue(req):
            return

        req.timed_out = True
        self._resolve_request(req, success=False, fail_node_id=node.id)

    def _on_failed(self, event: Event) -> None:
        node = self.architecture.get_node(event.node_id)
        req = event.request

        # Free the slot and promote the next queued request (if any)
        next_req = node.release()
        if next_req:
            self.schedule(self.current_time, EventType.PROCESSING_START, next_req, node.id)

        self._resolve_request(req, success=False, fail_node_id=node.id)
