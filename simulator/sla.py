from __future__ import annotations
from typing import Any


def check_sla(summary: dict, sla: dict) -> dict:
    results = []

    def _check(metric: str, actual: float, threshold: float) -> None:
        results.append({
            "metric":    metric,
            "threshold": threshold,
            "actual":    round(actual, 4),
            "passed":    actual <= threshold,
        })

    _GLOBAL = [
        ("avg_latency_ms", "max_avg_latency_ms"),
        ("p95_latency_ms", "max_p95_latency_ms"),
        ("p99_latency_ms", "max_p99_latency_ms"),
        ("failure_rate",   "max_failure_rate"),
        ("timed_out",      "max_timed_out"),
    ]
    for metric, key in _GLOBAL:
        if key in sla:
            _check(metric, summary.get(metric, 0), sla[key])

    for node_id, node_sla in sla.get("per_node", {}).items():
        nm = summary.get("node_metrics", {}).get(node_id, {})
        if "max_avg_utilization" in node_sla:
            _check(f"{node_id}.avg_utilization",
                   nm.get("avg_utilization", 0), node_sla["max_avg_utilization"])
        if "max_queue_size" in node_sla:
            _check(f"{node_id}.max_queue_size",
                   nm.get("max_queue_size", 0), node_sla["max_queue_size"])

    _TYPE_METRICS = [
        ("max_avg_latency_ms", "avg_latency_ms"),
        ("max_p95_latency_ms", "p95_latency_ms"),
        ("max_p99_latency_ms", "p99_latency_ms"),
        ("max_failure_rate",   "failure_rate"),
    ]
    for rtype, type_sla in sla.get("per_type", {}).items():
        bt = summary.get("by_type", {}).get(rtype, {})
        for key, metric in _TYPE_METRICS:
            if key in type_sla:
                _check(f"{rtype}.{metric}", bt.get(metric, 0), type_sla[key])

    violations    = [r for r in results if not r["passed"]]
    checks_passed = [r for r in results if r["passed"]]

    return {
        "passed":        len(violations) == 0,
        "total_checks":  len(results),
        "violations":    violations,
        "checks_passed": checks_passed,
    }
