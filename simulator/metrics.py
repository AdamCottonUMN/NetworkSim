from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from .request import Request


# ---------------------------------------------------------------------------
# Per-node accumulator
# ---------------------------------------------------------------------------

@dataclass
class NodeMetrics:
    node_id: str

    arrivals: int = 0
    completions: int = 0
    failures: int = 0

    _queue_size_samples: List[int] = field(default_factory=list, repr=False)
    _utilization_samples: List[float] = field(default_factory=list, repr=False)

    def record_queue_sample(self, size: int) -> None:
        self._queue_size_samples.append(size)

    def record_utilization(self, util: float) -> None:
        self._utilization_samples.append(util)

    @property
    def avg_queue_size(self) -> float:
        s = self._queue_size_samples
        return sum(s) / len(s) if s else 0.0

    @property
    def max_queue_size(self) -> int:
        return max(self._queue_size_samples, default=0)

    @property
    def avg_utilization(self) -> float:
        s = self._utilization_samples
        return sum(s) / len(s) if s else 0.0

    def to_dict(self) -> dict:
        return {
            "arrivals":        self.arrivals,
            "completions":     self.completions,
            "failures":        self.failures,
            "avg_utilization": round(self.avg_utilization, 4),
            "avg_queue_size":  round(self.avg_queue_size, 2),
            "max_queue_size":  self.max_queue_size,
        }


# ---------------------------------------------------------------------------
# Global metrics collector
# ---------------------------------------------------------------------------

@dataclass
class Metrics:
    """
    Collects all simulation telemetry.

    Time-series data
    ----------------
    _timeseries stores (time, value) pairs keyed by "<node_id>.queue_size"
    and "<node_id>.utilization". Use timeseries(key) to retrieve them.
    System-wide throughput is in "system.completed" and "system.failed".
    """

    completed_requests: List[Request] = field(default_factory=list, repr=False)
    failed_requests:    List[Request] = field(default_factory=list, repr=False)
    _node: Dict[str, NodeMetrics] = field(default_factory=dict, repr=False)
    _latencies: List[float] = field(default_factory=list, repr=False)
    _timeseries: Dict[str, List[Tuple[float, float]]] = field(default_factory=dict, repr=False)
    _latencies_by_type: Dict[str, List[float]] = field(default_factory=dict, repr=False)
    _completed_by_type: Dict[str, int] = field(default_factory=dict, repr=False)
    _failed_by_type: Dict[str, int] = field(default_factory=dict, repr=False)
    _timed_out_by_type: Dict[str, int] = field(default_factory=dict, repr=False)

    # --------------------------------------------------------- event callbacks

    def record_arrival(self, time: float, node_id: str, queue_size: int) -> None:
        nm = self._node_metrics(node_id)
        nm.arrivals += 1
        self._ts(f"{node_id}.queue_size", time, queue_size)

    def record_queued(self, time: float, node_id: str, queue_size: int) -> None:
        nm = self._node_metrics(node_id)
        nm.record_queue_sample(queue_size)
        self._ts(f"{node_id}.queue_size", time, queue_size)

    def record_processing_start(self, time: float, node_id: str, utilization: float) -> None:
        nm = self._node_metrics(node_id)
        nm.record_utilization(utilization)
        self._ts(f"{node_id}.utilization", time, utilization)

    def record_processing_complete(
        self, time: float, node_id: str, utilization: float, queue_size: int = 0
    ) -> None:
        nm = self._node_metrics(node_id)
        nm.completions += 1
        nm.record_utilization(utilization)
        nm.record_queue_sample(queue_size)
        self._ts(f"{node_id}.utilization", time, utilization)
        self._ts(f"{node_id}.queue_size", time, queue_size)

    def record_completion(self, time: float, request: Request) -> None:
        self.completed_requests.append(request)
        rtype = request.request_type
        if request.total_latency is not None:
            self._latencies.append(request.total_latency)
            self._latencies_by_type.setdefault(rtype, []).append(request.total_latency)
        self._completed_by_type[rtype] = self._completed_by_type.get(rtype, 0) + 1
        self._ts("system.completed", time, len(self.completed_requests))

    def record_node_down(self, time: float, node_id: str) -> None:
        self._ts(f"{node_id}.is_down", time, 1.0)

    def record_node_up(self, time: float, node_id: str) -> None:
        self._ts(f"{node_id}.is_down", time, 0.0)

    def record_failure(self, time: float, node_id: str, request: Request) -> None:
        nm = self._node_metrics(node_id)
        nm.failures += 1
        self.failed_requests.append(request)
        rtype = request.request_type
        self._failed_by_type[rtype] = self._failed_by_type.get(rtype, 0) + 1
        if request.timed_out:
            self._timed_out_by_type[rtype] = self._timed_out_by_type.get(rtype, 0) + 1
        self._ts("system.failed", time, len(self.failed_requests))

    # ------------------------------------------------------------ time-series

    def timeseries(self, key: str) -> List[Tuple[float, float]]:
        """Return (time, value) pairs for a given key, e.g. 'db.queue_size'."""
        return self._timeseries.get(key, [])

    def timeseries_keys(self) -> List[str]:
        return list(self._timeseries.keys())

    def _ts(self, key: str, time: float, value: float) -> None:
        self._timeseries.setdefault(key, []).append((time, value))

    # ------------------------------------------------------------ summary

    def summary(self) -> dict:
        total = len(self.completed_requests) + len(self.failed_requests)
        lat = sorted(self._latencies)

        def percentile(data: list, p: float) -> float:
            if not data:
                return 0.0
            idx = int(len(data) * p / 100)
            return data[min(idx, len(data) - 1)]

        timed_out = sum(1 for r in self.failed_requests if r.timed_out)

        all_types = sorted(set(self._completed_by_type) | set(self._failed_by_type))
        by_type = {}
        for rtype in all_types:
            tlat = sorted(self._latencies_by_type.get(rtype, []))
            c = self._completed_by_type.get(rtype, 0)
            f = self._failed_by_type.get(rtype, 0)
            by_type[rtype] = {
                "completed":      c,
                "failed":         f,
                "timed_out":      self._timed_out_by_type.get(rtype, 0),
                "failure_rate":   f / (c + f) if (c + f) else 0.0,
                "avg_latency_ms": (sum(tlat) / len(tlat) * 1000) if tlat else 0.0,
                "p50_latency_ms": percentile(tlat, 50) * 1000,
                "p95_latency_ms": percentile(tlat, 95) * 1000,
                "p99_latency_ms": percentile(tlat, 99) * 1000,
            }

        return {
            "total_requests":   total,
            "completed":        len(self.completed_requests),
            "failed":           len(self.failed_requests),
            "timed_out":        timed_out,
            "failure_rate":     len(self.failed_requests) / total if total else 0.0,
            "avg_latency_ms":   (sum(lat) / len(lat) * 1000) if lat else 0.0,
            "p50_latency_ms":   percentile(lat, 50) * 1000,
            "p95_latency_ms":   percentile(lat, 95) * 1000,
            "p99_latency_ms":   percentile(lat, 99) * 1000,
            "by_type":          by_type,
            "node_metrics":     {nid: nm.to_dict() for nid, nm in self._node.items()},
        }

    # ------------------------------------------------------------ helpers

    def _node_metrics(self, node_id: str) -> NodeMetrics:
        if node_id not in self._node:
            self._node[node_id] = NodeMetrics(node_id=node_id)
        return self._node[node_id]

    def reset(self) -> None:
        self.completed_requests.clear()
        self.failed_requests.clear()
        self._node.clear()
        self._latencies.clear()
        self._timeseries.clear()
        self._latencies_by_type.clear()
        self._completed_by_type.clear()
        self._failed_by_type.clear()
        self._timed_out_by_type.clear()
