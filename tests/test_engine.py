"""
Basic unit / integration tests for the simulation engine.

Run with: python -m pytest tests/ -v
"""

import heapq
import pytest

import io
import json
import tempfile
from pathlib import Path

from simulator.architecture import Architecture, RoutingStrategy
from simulator.engine import SimulationEngine, EventType
from simulator.export import export_csv, export_json, summary_to_csv_bytes, summary_to_json_bytes
from simulator.metrics import Metrics
from simulator.node import Node
from simulator.request import Request, RequestStatus
from simulator.sla import check_sla
from traffic.generators import mixed_arrivals, poisson_arrivals


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def two_node_arch() -> Architecture:
    """lb → app (no failures, deterministic-ish times)."""
    return Architecture.linear_chain("test", [
        {"id": "lb",  "name": "Load Balancer", "capacity": 10, "mean_processing_time": 0.01, "std_processing_time": 0.0},
        {"id": "app", "name": "App Server",    "capacity": 5,  "mean_processing_time": 0.05, "std_processing_time": 0.0},
    ])


def push_events(engine, events):
    for ev in events:
        heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
        engine._counter += 1


# ---------------------------------------------------------------------------
# Request
# ---------------------------------------------------------------------------

class TestRequest:
    def test_defaults(self):
        req = Request()
        assert req.status == RequestStatus.PENDING
        assert req.path == []
        assert req.total_latency is None

    def test_latency_computed(self):
        req = Request(created_at=0.0)
        req.completed_at = 0.5
        assert req.total_latency == pytest.approx(0.5)

    def test_unique_ids(self):
        ids = {Request().id for _ in range(1000)}
        assert len(ids) == 1000


# ---------------------------------------------------------------------------
# Node
# ---------------------------------------------------------------------------

class TestNode:
    def test_accept_within_capacity(self):
        node = Node(id="n", name="N", capacity=2)
        req = Request()
        assert node.accept(req) is True
        assert node.active_requests == 1
        assert node.queue_size == 0

    def test_accept_at_capacity_queues(self):
        node = Node(id="n", name="N", capacity=1)
        r1, r2 = Request(), Request()
        assert node.accept(r1) is True
        assert node.accept(r2) is False   # queued
        assert node.queue_size == 1

    def test_release_promotes_queued(self):
        node = Node(id="n", name="N", capacity=1)
        r1, r2 = Request(), Request()
        node.accept(r1)
        node.accept(r2)   # r2 queued
        promoted = node.release()
        assert promoted is r2
        assert node.active_requests == 1
        assert node.queue_size == 0

    def test_release_empty_queue(self):
        node = Node(id="n", name="N", capacity=2)
        node.accept(Request())
        assert node.release() is None

    def test_utilization(self):
        node = Node(id="n", name="N", capacity=4)
        node.accept(Request())
        node.accept(Request())
        assert node.utilization == pytest.approx(0.5)


# ---------------------------------------------------------------------------
# Engine + Architecture integration
# ---------------------------------------------------------------------------

class TestSimulation:
    def _run(self, arch, rate=10, duration=5.0, seed=0):
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id=arch.entry_node_id, seed=seed)
        push_events(engine, events)
        engine.run(until=duration)
        return metrics

    def test_all_requests_complete_or_fail(self):
        arch = two_node_arch()
        m = self._run(arch, rate=5, duration=5.0)
        s = m.summary()
        assert s["completed"] + s["failed"] == s["total_requests"]

    def test_requests_traverse_full_path(self):
        arch = two_node_arch()
        m = self._run(arch, rate=5, duration=5.0)
        for req in m.completed_requests:
            assert req.path == ["lb", "app"], f"Unexpected path: {req.path}"

    def test_completed_requests_have_latency(self):
        arch = two_node_arch()
        m = self._run(arch, rate=5, duration=5.0)
        for req in m.completed_requests:
            assert req.total_latency is not None
            assert req.total_latency > 0

    def test_failure_rate_respected(self):
        arch = Architecture.linear_chain("fail_test", [
            {"id": "flaky", "name": "Flaky Node", "capacity": 50,
             "mean_processing_time": 0.01, "std_processing_time": 0.0,
             "failure_rate": 0.5},
        ])
        m = self._run(arch, rate=50, duration=10.0, seed=1)
        s = m.summary()
        # With failure_rate=0.5 we expect ~50% failures (±15% tolerance)
        assert 0.35 < s["failure_rate"] < 0.65

    def test_zero_failures_by_default(self):
        arch = two_node_arch()   # failure_rate=0.0
        m = self._run(arch, rate=5, duration=5.0)
        assert m.summary()["failed"] == 0

    def test_node_metrics_populated(self):
        arch = two_node_arch()
        m = self._run(arch, rate=10, duration=5.0)
        s = m.summary()
        assert "lb" in s["node_metrics"]
        assert "app" in s["node_metrics"]
        assert s["node_metrics"]["lb"]["arrivals"] > 0

    def test_high_load_creates_queue(self):
        """At high load the bottleneck node's max_queue_size should be > 0."""
        arch = Architecture.linear_chain("bottleneck", [
            {"id": "lb",  "name": "LB",  "capacity": 100, "mean_processing_time": 0.001, "std_processing_time": 0.0},
            {"id": "db",  "name": "DB",  "capacity": 2,   "mean_processing_time": 0.5,   "std_processing_time": 0.0},
        ])
        m = self._run(arch, rate=50, duration=5.0)
        s = m.summary()
        assert s["node_metrics"]["db"]["max_queue_size"] > 0


# ---------------------------------------------------------------------------
# Traffic generators
# ---------------------------------------------------------------------------

class TestGenerators:
    def test_poisson_count_roughly_correct(self):
        events = poisson_arrivals(rate=100, duration=10.0, entry_node_id="lb", seed=42)
        # Expect ~1000 events; allow generous tolerance
        assert 700 < len(events) < 1300

    def test_events_are_sorted(self):
        events = poisson_arrivals(rate=50, duration=5.0, entry_node_id="lb", seed=0)
        times = [e.time for e in events]
        assert times == sorted(times)

    def test_all_events_within_duration(self):
        events = poisson_arrivals(rate=20, duration=3.0, entry_node_id="lb")
        assert all(e.time < 3.0 for e in events)

    def test_seed_reproducibility(self):
        e1 = poisson_arrivals(rate=10, duration=5.0, entry_node_id="lb", seed=7)
        e2 = poisson_arrivals(rate=10, duration=5.0, entry_node_id="lb", seed=7)
        assert [ev.time for ev in e1] == [ev.time for ev in e2]

    def test_mixed_arrivals_all_types_present(self):
        mix = {"login": 1, "page_load": 2, "data_fetch": 1}
        events = mixed_arrivals(rate=50, duration=10.0, entry_node_id="lb", mix=mix, seed=0)
        types_seen = {ev.request.request_type for ev in events}
        assert types_seen == {"login", "page_load", "data_fetch"}

    def test_mixed_arrivals_proportions_roughly_correct(self):
        mix = {"login": 0.2, "page_load": 0.5, "data_fetch": 0.3}
        events = mixed_arrivals(rate=200, duration=30.0, entry_node_id="lb", mix=mix, seed=1)
        total = len(events)
        counts = {}
        for ev in events:
            rtype = ev.request.request_type
            counts[rtype] = counts.get(rtype, 0) + 1
        assert 0.12 < counts["login"]      / total < 0.28
        assert 0.40 < counts["page_load"]  / total < 0.60
        assert 0.22 < counts["data_fetch"] / total < 0.38

    def test_mixed_arrivals_sorted(self):
        events = mixed_arrivals(rate=50, duration=5.0, entry_node_id="lb",
                                mix={"a": 1, "b": 1}, seed=0)
        times = [ev.time for ev in events]
        assert times == sorted(times)

    def test_mixed_arrivals_seed_reproducible(self):
        mix = {"login": 1, "page_load": 2}
        e1 = mixed_arrivals(rate=20, duration=5.0, entry_node_id="lb", mix=mix, seed=9)
        e2 = mixed_arrivals(rate=20, duration=5.0, entry_node_id="lb", mix=mix, seed=9)
        assert [(ev.time, ev.request.request_type) for ev in e1] == \
               [(ev.time, ev.request.request_type) for ev in e2]


# ---------------------------------------------------------------------------
# Timeouts
# ---------------------------------------------------------------------------

class TestTimeouts:
    def _run(self, timeout, rate, duration=5.0, seed=0):
        arch = Architecture.linear_chain("to_test", [
            {"id": "front", "name": "Front", "capacity": 1,
             "mean_processing_time": 1.0, "std_processing_time": 0.0,
             "timeout": timeout},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id="front", seed=seed)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_timeouts_fire_under_load(self):
        m = self._run(timeout=0.1, rate=20)
        s = m.summary()
        assert s["timed_out"] > 0

    def test_timed_out_requests_are_failed(self):
        m = self._run(timeout=0.1, rate=20)
        s = m.summary()
        assert s["timed_out"] <= s["failed"]

    def test_timed_out_flag_set_on_request(self):
        m = self._run(timeout=0.1, rate=20)
        assert all(r.timed_out for r in m.failed_requests)

    def test_no_timeout_no_drops(self):
        m = self._run(timeout=None, rate=2, duration=3.0)
        assert m.summary()["timed_out"] == 0

    def test_generous_timeout_no_drops(self):
        m = self._run(timeout=999.0, rate=2, duration=3.0)
        assert m.summary()["timed_out"] == 0


# ---------------------------------------------------------------------------
# Routing strategies
# ---------------------------------------------------------------------------

class TestRouting:
    def _arch_parallel(self, strategy: RoutingStrategy) -> Architecture:
        """lb --(strategy)--> app1, app2. Each app -> done."""
        arch = Architecture(name="parallel")
        arch.add_node(Node(id="lb",   name="LB",   capacity=100, mean_processing_time=0.001, std_processing_time=0.0))
        arch.add_node(Node(id="app1", name="App1", capacity=50,  mean_processing_time=0.01,  std_processing_time=0.0))
        arch.add_node(Node(id="app2", name="App2", capacity=50,  mean_processing_time=0.01,  std_processing_time=0.0))
        arch.add_edge("lb", "app1")
        arch.add_edge("lb", "app2")
        arch.set_routing("lb", strategy)
        return arch

    def _run(self, arch, rate=20, duration=10.0, seed=0):
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id="lb", seed=seed)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_round_robin_distributes_evenly(self):
        arch = self._arch_parallel(RoutingStrategy.ROUND_ROBIN)
        m = self._run(arch, rate=100, duration=5.0)
        s = m.summary()
        a1 = s["node_metrics"]["app1"]["arrivals"]
        a2 = s["node_metrics"]["app2"]["arrivals"]
        # Should be within 1 of each other (perfect alternation)
        assert abs(a1 - a2) <= 1

    def test_random_routing_uses_both_nodes(self):
        arch = self._arch_parallel(RoutingStrategy.RANDOM)
        m = self._run(arch, rate=100, duration=5.0, seed=42)
        s = m.summary()
        assert s["node_metrics"]["app1"]["arrivals"] > 0
        assert s["node_metrics"]["app2"]["arrivals"] > 0

    def test_weighted_routing_respects_bias(self):
        arch = self._arch_parallel(RoutingStrategy.WEIGHTED)
        arch.set_routing("lb", RoutingStrategy.WEIGHTED, weights={"app1": 9, "app2": 1})
        m = self._run(arch, rate=200, duration=10.0, seed=1)
        s = m.summary()
        a1 = s["node_metrics"]["app1"]["arrivals"]
        a2 = s["node_metrics"]["app2"]["arrivals"]
        # app1 should receive ~90% — check it's at least 3x more than app2
        assert a1 > a2 * 3

    def test_first_strategy_always_picks_first(self):
        arch = self._arch_parallel(RoutingStrategy.FIRST)
        m = self._run(arch, rate=100, duration=5.0)
        s = m.summary()
        # app2 should never be reached
        assert s["node_metrics"].get("app2", {}).get("arrivals", 0) == 0


# ---------------------------------------------------------------------------
# Node outages
# ---------------------------------------------------------------------------

class TestOutages:
    def _simple_arch(self):
        return Architecture.linear_chain("outage_test", [
            {"id": "app", "name": "App", "capacity": 10,
             "mean_processing_time": 0.01, "std_processing_time": 0.0},
        ])

    def _run(self, arch, rate=20, duration=10.0, seed=0, outages=None):
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id="app", seed=seed)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        if outages:
            for node_id, start, dur in outages:
                engine.schedule_outage(node_id, start, dur)
        engine.run(until=duration)
        return metrics

    def test_outage_causes_failures(self):
        arch = self._simple_arch()
        m = self._run(arch, outages=[("app", 3.0, 2.0)])
        assert m.summary()["failed"] > 0

    def test_no_outage_no_failures(self):
        arch = self._simple_arch()
        m = self._run(arch)
        assert m.summary()["failed"] == 0

    def test_failures_only_during_outage_window(self):
        arch = self._simple_arch()
        m = self._run(arch, rate=30, duration=15.0, outages=[("app", 5.0, 3.0)])
        for req in m.failed_requests:
            assert 5.0 <= req.failed_at < 8.0

    def test_node_recovers_after_outage(self):
        arch = self._simple_arch()
        m = self._run(arch, rate=10, duration=15.0, outages=[("app", 2.0, 3.0)])
        s = m.summary()
        post_outage = [r for r in m.completed_requests if r.completed_at and r.completed_at > 5.0]
        assert len(post_outage) > 0

    def test_queued_requests_drain_on_recovery(self):
        arch = Architecture.linear_chain("drain_test", [
            {"id": "app", "name": "App", "capacity": 2,
             "mean_processing_time": 0.5, "std_processing_time": 0.0},
        ])
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=10, duration=5.0, entry_node_id="app", seed=0)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.schedule_outage("app", start=1.0, duration=2.0)
        engine.run(until=20.0)
        node = arch.get_node("app")
        assert node.queue_size == 0

    def test_outage_timeseries_recorded(self):
        arch = self._simple_arch()
        m = self._run(arch, outages=[("app", 2.0, 3.0)])
        series = m.timeseries("app.is_down")
        assert len(series) == 2
        times  = [t for t, _ in series]
        values = [v for _, v in series]
        assert times[0] == pytest.approx(2.0)
        assert times[1] == pytest.approx(5.0)
        assert values == [1.0, 0.0]


# ---------------------------------------------------------------------------
# Cache hit / miss
# ---------------------------------------------------------------------------

class TestCache:
    def _cache_arch(self, hit_rate: float) -> Architecture:
        """app -> cache (hit_rate) -> db"""
        return Architecture.linear_chain("cache_test", [
            {"id": "app",   "name": "App",   "capacity": 50, "mean_processing_time": 0.005, "std_processing_time": 0.0},
            {"id": "cache", "name": "Cache", "capacity": 50, "mean_processing_time": 0.001, "std_processing_time": 0.0, "hit_rate": hit_rate},
            {"id": "db",    "name": "DB",    "capacity": 50, "mean_processing_time": 0.01,  "std_processing_time": 0.0},
        ])

    def _run(self, arch, rate=50, duration=10.0, seed=0):
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id="app", seed=seed)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_full_hit_rate_never_reaches_db(self):
        arch = self._cache_arch(hit_rate=1.0)
        m = self._run(arch)
        s = m.summary()
        assert s["node_metrics"].get("db", {}).get("arrivals", 0) == 0
        assert s["completed"] > 0

    def test_zero_hit_rate_always_reaches_db(self):
        arch = self._cache_arch(hit_rate=0.0)
        m = self._run(arch)
        s = m.summary()
        assert s["node_metrics"]["db"]["arrivals"] > 0

    def test_partial_hit_rate_reduces_db_load(self):
        """DB arrivals with 80% hit rate should be ~20% of cache arrivals."""
        arch = self._cache_arch(hit_rate=0.8)
        m = self._run(arch, rate=200, duration=10.0, seed=42)
        s = m.summary()
        cache_arrivals = s["node_metrics"]["cache"]["arrivals"]
        db_arrivals    = s["node_metrics"]["db"]["arrivals"]
        ratio = db_arrivals / cache_arrivals
        # Expect ~20% ± 10%
        assert 0.10 < ratio < 0.30


# ---------------------------------------------------------------------------
# Time-series metrics
# ---------------------------------------------------------------------------

class TestTimeSeries:
    def test_queue_size_timeseries_recorded(self):
        arch = Architecture.linear_chain("ts_test", [
            {"id": "slow", "name": "Slow", "capacity": 1, "mean_processing_time": 0.5, "std_processing_time": 0.0},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=10, duration=5.0, entry_node_id="slow", seed=0)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=5.0)

        series = metrics.timeseries("slow.queue_size")
        assert len(series) > 0
        # Each entry is a (time, value) tuple
        for t, v in series:
            assert t >= 0
            assert v >= 0

    def test_utilization_timeseries_recorded(self):
        arch = Architecture.linear_chain("ts_test", [
            {"id": "n", "name": "N", "capacity": 5, "mean_processing_time": 0.05, "std_processing_time": 0.0},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=20, duration=5.0, entry_node_id="n", seed=0)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=5.0)

        series = metrics.timeseries("n.utilization")
        assert len(series) > 0
        for _, v in series:
            assert 0.0 <= v <= 1.0


# ---------------------------------------------------------------------------
# Per-request-type metrics
# ---------------------------------------------------------------------------

class TestByType:
    def _run_mixed(self, rates: dict, duration=10.0, seed=0):
        arch = Architecture.linear_chain("type_test", [
            {"id": "app", "name": "App", "capacity": 20,
             "mean_processing_time": 0.05, "std_processing_time": 0.0},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        for rtype, rate in rates.items():
            for ev in poisson_arrivals(rate, duration, "app", request_type=rtype, seed=seed):
                heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
                engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_by_type_keys_match_request_types(self):
        m = self._run_mixed({"login": 5, "page_load": 10, "data_fetch": 8})
        s = m.summary()
        assert set(s["by_type"].keys()) == {"login", "page_load", "data_fetch"}

    def test_by_type_counts_sum_to_total(self):
        m = self._run_mixed({"login": 5, "page_load": 10})
        s = m.summary()
        total_completed = sum(bt["completed"] for bt in s["by_type"].values())
        total_failed    = sum(bt["failed"]    for bt in s["by_type"].values())
        assert total_completed == s["completed"]
        assert total_failed    == s["failed"]

    def test_single_type_has_latency(self):
        m = self._run_mixed({"data_fetch": 10})
        s = m.summary()
        assert s["by_type"]["data_fetch"]["avg_latency_ms"] > 0

    def test_different_processing_times_produce_different_latencies(self):
        arch = Architecture.linear_chain("profile_test", [
            {"id": "app", "name": "App", "capacity": 50,
             "mean_processing_time": 0.05, "std_processing_time": 0.0,
             "processing_profiles": {
                 "login":      [0.2, 0.0],
                 "data_fetch": [0.02, 0.0],
             }},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        for rtype in ["login", "data_fetch"]:
            for ev in poisson_arrivals(10, 10.0, "app", request_type=rtype, seed=0):
                heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
                engine._counter += 1
        engine.run(until=10.0)
        s = metrics.summary()
        assert s["by_type"]["login"]["avg_latency_ms"] > s["by_type"]["data_fetch"]["avg_latency_ms"]

    def test_timed_out_counted_per_type(self):
        arch = Architecture.linear_chain("to_type_test", [
            {"id": "slow", "name": "Slow", "capacity": 1,
             "mean_processing_time": 1.0, "std_processing_time": 0.0,
             "timeout": 0.1},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        for ev in poisson_arrivals(20, 5.0, "slow", request_type="login", seed=0):
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=5.0)
        s = metrics.summary()
        assert s["by_type"]["login"]["timed_out"] > 0
        assert s["by_type"]["login"]["timed_out"] == s["timed_out"]


# ---------------------------------------------------------------------------
# SLA checks
# ---------------------------------------------------------------------------

class TestSLA:
    BASE_SUMMARY = {
        "total_requests": 1000,
        "completed": 990,
        "failed": 10,
        "timed_out": 0,
        "failure_rate": 0.01,
        "avg_latency_ms": 120.0,
        "p95_latency_ms": 200.0,
        "p99_latency_ms": 280.0,
        "by_type": {
            "login":      {"avg_latency_ms": 180.0, "p95_latency_ms": 300.0,
                           "p99_latency_ms": 400.0, "failure_rate": 0.01},
            "data_fetch": {"avg_latency_ms":  50.0, "p95_latency_ms":  80.0,
                           "p99_latency_ms": 100.0, "failure_rate": 0.005},
        },
        "node_metrics": {
            "db": {"avg_utilization": 0.75, "max_queue_size": 3},
        },
    }

    def test_all_pass_when_within_thresholds(self):
        sla = {"max_p99_latency_ms": 300, "max_failure_rate": 0.02}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is True
        assert len(report["violations"]) == 0

    def test_violation_when_p99_exceeded(self):
        sla = {"max_p99_latency_ms": 200}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "p99_latency_ms" for v in report["violations"])

    def test_violation_when_failure_rate_exceeded(self):
        sla = {"max_failure_rate": 0.005}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "failure_rate" for v in report["violations"])

    def test_per_node_utilization_violation(self):
        sla = {"per_node": {"db": {"max_avg_utilization": 0.5}}}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "db.avg_utilization" for v in report["violations"])

    def test_per_node_queue_violation(self):
        sla = {"per_node": {"db": {"max_queue_size": 2}}}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "db.max_queue_size" for v in report["violations"])

    def test_per_type_violation(self):
        sla = {"per_type": {"login": {"max_p99_latency_ms": 300}}}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "login.p99_latency_ms" for v in report["violations"])

    def test_per_type_passes(self):
        sla = {"per_type": {"data_fetch": {"max_p99_latency_ms": 150}}}
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["passed"] is True

    def test_total_checks_count(self):
        sla = {
            "max_p99_latency_ms": 300,
            "max_failure_rate": 0.02,
            "per_node": {"db": {"max_avg_utilization": 0.9}},
            "per_type": {"login": {"max_p99_latency_ms": 500}},
        }
        report = check_sla(self.BASE_SUMMARY, sla)
        assert report["total_checks"] == 4

    def test_empty_sla_always_passes(self):
        report = check_sla(self.BASE_SUMMARY, {})
        assert report["passed"] is True
        assert report["total_checks"] == 0

    def test_timed_out_threshold(self):
        summary = {**self.BASE_SUMMARY, "timed_out": 5}
        sla = {"max_timed_out": 0}
        report = check_sla(summary, sla)
        assert report["passed"] is False
        assert any(v["metric"] == "timed_out" for v in report["violations"])


# ---------------------------------------------------------------------------
# Fan-out / scatter-gather
# ---------------------------------------------------------------------------

class TestFanOut:
    def _scatter_arch(self, fail_rate_auth=0.0, fail_rate_product=0.0):
        """gateway (fan_out) → auth + product (leaf nodes)."""
        arch = Architecture(name="scatter")
        arch.add_node(Node(id="gateway", name="Gateway", capacity=200,
                           mean_processing_time=0.001, std_processing_time=0.0,
                           fan_out=True))
        arch.add_node(Node(id="auth",    name="Auth",    capacity=50,
                           mean_processing_time=0.01, std_processing_time=0.0,
                           failure_rate=fail_rate_auth))
        arch.add_node(Node(id="product", name="Product", capacity=50,
                           mean_processing_time=0.02, std_processing_time=0.0,
                           failure_rate=fail_rate_product))
        arch.add_edge("gateway", "auth")
        arch.add_edge("gateway", "product")
        return arch

    def _run(self, arch, rate=20, duration=5.0, seed=0):
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=rate, duration=duration, entry_node_id="gateway", seed=seed)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_fanout_delivers_to_all_branches(self):
        """Each parent request spawns one child per outgoing edge."""
        arch = self._scatter_arch()
        m = self._run(arch, rate=50, duration=5.0)
        s = m.summary()
        auth_arr    = s["node_metrics"]["auth"]["arrivals"]
        product_arr = s["node_metrics"]["product"]["arrivals"]
        # Both branches always receive the same number of children
        # (fan-out dispatches to both simultaneously)
        assert auth_arr == product_arr
        # Each branch receives at least as many requests as completed parents
        assert auth_arr >= s["completed"]

    def test_fanout_all_complete_with_no_failures(self):
        arch = self._scatter_arch()
        m = self._run(arch, rate=20, duration=5.0)
        s = m.summary()
        assert s["completed"] == s["total_requests"]
        assert s["failed"] == 0

    def test_fanout_children_not_double_counted(self):
        """total_requests counts parents only, not the child sub-requests."""
        arch = self._scatter_arch()
        m = self._run(arch, rate=20, duration=5.0)
        s = m.summary()
        # gateway.arrivals == total_requests (parents only arrive at gateway)
        assert s["node_metrics"]["gateway"]["arrivals"] == s["total_requests"]

    def test_fanout_latency_reflects_slowest_branch(self):
        """End-to-end latency must be >= the slowest branch (product at 20ms)."""
        arch = self._scatter_arch()
        m = self._run(arch, rate=10, duration=5.0, seed=1)
        s = m.summary()
        # gateway=1ms, auth=10ms, product=20ms → total ≥ 21ms
        assert s["avg_latency_ms"] >= 20.0

    def test_fanout_parent_fails_when_child_fails(self):
        """If any branch fails, the parent request must be recorded as failed."""
        arch = self._scatter_arch(fail_rate_product=1.0)  # product always fails
        m = self._run(arch, rate=20, duration=5.0)
        s = m.summary()
        # All requests should fail because the product branch always fails
        assert s["failed"] > 0
        assert s["completed"] == 0

    def test_fanout_disabled_routes_to_one(self):
        """With fan_out=False the gateway uses normal routing (goes to first only)."""
        arch = Architecture(name="no_fanout")
        arch.add_node(Node(id="gateway", name="Gateway", capacity=200,
                           mean_processing_time=0.001, std_processing_time=0.0,
                           fan_out=False))
        arch.add_node(Node(id="auth",    name="Auth",    capacity=50,
                           mean_processing_time=0.01, std_processing_time=0.0))
        arch.add_node(Node(id="product", name="Product", capacity=50,
                           mean_processing_time=0.02, std_processing_time=0.0))
        arch.add_edge("gateway", "auth")
        arch.add_edge("gateway", "product")
        # Default routing is FIRST → only auth receives traffic
        arch.reset()
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        events = poisson_arrivals(rate=50, duration=5.0, entry_node_id="gateway", seed=0)
        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=5.0)
        s = metrics.summary()
        assert s["node_metrics"]["auth"]["arrivals"] > 0
        assert s["node_metrics"].get("product", {}).get("arrivals", 0) == 0


# ---------------------------------------------------------------------------
# Export
# ---------------------------------------------------------------------------

class TestExport:
    def _run_sim(self, rate=20, duration=5.0, seed=0):
        arch = Architecture.linear_chain("export_test", [
            {"id": "app", "name": "App", "capacity": 10,
             "mean_processing_time": 0.05, "std_processing_time": 0.0},
        ])
        metrics = Metrics()
        engine = SimulationEngine(arch, metrics)
        for ev in poisson_arrivals(rate, duration, "app", seed=seed):
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1
        engine.run(until=duration)
        return metrics

    def test_export_json_file_is_valid_json(self):
        m = self._run_sim()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        export_json(m, path)
        data = json.loads(Path(path).read_text())
        assert "summary" in data
        assert "requests" in data

    def test_export_json_request_count_matches(self):
        m = self._run_sim()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        export_json(m, path)
        data = json.loads(Path(path).read_text())
        total = m.summary()["total_requests"]
        assert len(data["requests"]) == total

    def test_export_json_request_fields(self):
        m = self._run_sim()
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        export_json(m, path)
        data = json.loads(Path(path).read_text())
        req = data["requests"][0]
        for field in ("id", "request_type", "status", "created_at", "timed_out", "path"):
            assert field in req

    def test_export_csv_file_has_header(self):
        m = self._run_sim()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        export_csv(m, path)
        lines = Path(path).read_text().splitlines()
        assert lines[0].startswith("id,")

    def test_export_csv_row_count_matches(self):
        m = self._run_sim()
        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w") as f:
            path = f.name
        export_csv(m, path)
        lines = Path(path).read_text().splitlines()
        total = m.summary()["total_requests"]
        assert len(lines) - 1 == total  # subtract header

    def test_summary_to_json_bytes_is_valid(self):
        m = self._run_sim()
        raw = summary_to_json_bytes(m)
        assert isinstance(raw, bytes)
        data = json.loads(raw)
        assert "summary" in data
        assert "requests" in data

    def test_summary_to_csv_bytes_is_valid(self):
        m = self._run_sim()
        raw = summary_to_csv_bytes(m)
        assert isinstance(raw, bytes)
        text = raw.decode()
        assert "id" in text.splitlines()[0]

    def test_completed_request_has_latency(self):
        m = self._run_sim()
        raw = summary_to_json_bytes(m)
        data = json.loads(raw)
        completed = [r for r in data["requests"] if r["status"] == "completed"]
        assert all(r["total_latency_ms"] is not None for r in completed)

    def test_path_encoded_in_csv(self):
        m = self._run_sim()
        raw = summary_to_csv_bytes(m)
        text = raw.decode()
        rows = text.splitlines()
        assert len(rows) > 1
        assert "app" in rows[1]
