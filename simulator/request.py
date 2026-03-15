from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, TYPE_CHECKING
import uuid

if TYPE_CHECKING:
    pass  # kept for future imports


class RequestStatus(Enum):
    PENDING    = "pending"
    QUEUED     = "queued"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


@dataclass
class Request:
    """A single unit of work flowing through the architecture."""

    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    request_type: str = "http"
    created_at: float = 0.0
    status: RequestStatus = RequestStatus.PENDING

    # Lifecycle timestamps (set by the engine as events fire)
    queued_at: Optional[float] = None
    processing_started_at: Optional[float] = None
    completed_at: Optional[float] = None
    failed_at: Optional[float] = None
    timed_out: bool = False

    # Routing history
    path: List[str] = field(default_factory=list)   # node IDs visited, in order
    current_node: Optional[str] = None

    # Fan-out tracking (set by engine; ignored for non-fan-out requests)
    parent_req: Optional['Request'] = field(default=None, repr=False)
    pending_children: int = 0   # decremented as child requests complete

    # ------------------------------------------------------------------ metrics

    @property
    def total_latency(self) -> Optional[float]:
        """Wall-clock time from creation to completion."""
        if self.completed_at is not None:
            return self.completed_at - self.created_at
        return None

    @property
    def queue_wait_time(self) -> Optional[float]:
        """Total time spent waiting in queues (across all nodes)."""
        if self.queued_at is not None and self.processing_started_at is not None:
            return self.processing_started_at - self.queued_at
        return None

    def __repr__(self) -> str:
        return (
            f"Request(id={self.id!r}, type={self.request_type!r}, "
            f"status={self.status.value}, path={self.path})"
        )
