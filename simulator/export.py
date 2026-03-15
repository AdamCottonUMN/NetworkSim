from __future__ import annotations
import csv
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .metrics import Metrics


def export_json(metrics: "Metrics", path: str | Path) -> None:
    summary = metrics.summary()
    all_requests = []
    for req in metrics.completed_requests + metrics.failed_requests:
        tl = req.total_latency
        qw = req.queue_wait_time
        all_requests.append({
            "id":                req.id,
            "request_type":      req.request_type,
            "status":            req.status.value,
            "created_at":        req.created_at,
            "completed_at":      req.completed_at,
            "failed_at":         req.failed_at,
            "timed_out":         req.timed_out,
            "total_latency_ms":  round(tl * 1000, 4) if tl is not None else None,
            "queue_wait_ms":     round(qw * 1000, 4) if qw is not None else None,
            "path":              req.path,
        })

    payload = {"summary": summary, "requests": all_requests}
    Path(path).write_text(json.dumps(payload, indent=2))


def export_csv(metrics: "Metrics", path: str | Path) -> None:
    fieldnames = [
        "id", "request_type", "status", "created_at",
        "total_latency_ms", "queue_wait_ms", "timed_out", "path",
    ]
    all_requests = metrics.completed_requests + metrics.failed_requests
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for req in all_requests:
            tl = req.total_latency
            qw = req.queue_wait_time
            writer.writerow({
                "id":               req.id,
                "request_type":     req.request_type,
                "status":           req.status.value,
                "created_at":       req.created_at,
                "total_latency_ms": round(tl * 1000, 4) if tl is not None else "",
                "queue_wait_ms":    round(qw * 1000, 4) if qw is not None else "",
                "timed_out":        req.timed_out,
                "path":             ">".join(req.path),
            })


def summary_to_json_bytes(metrics: "Metrics") -> bytes:
    summary = metrics.summary()
    all_requests = []
    for req in metrics.completed_requests + metrics.failed_requests:
        tl = req.total_latency
        qw = req.queue_wait_time
        all_requests.append({
            "id":               req.id,
            "request_type":     req.request_type,
            "status":           req.status.value,
            "created_at":       req.created_at,
            "timed_out":        req.timed_out,
            "total_latency_ms": round(tl * 1000, 4) if tl is not None else None,
            "queue_wait_ms":    round(qw * 1000, 4) if qw is not None else None,
            "path":             req.path,
        })
    return json.dumps({"summary": summary, "requests": all_requests}, indent=2).encode()


def summary_to_csv_bytes(metrics: "Metrics") -> bytes:
    import io
    fieldnames = [
        "id", "request_type", "status", "created_at",
        "total_latency_ms", "queue_wait_ms", "timed_out", "path",
    ]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=fieldnames)
    writer.writeheader()
    for req in metrics.completed_requests + metrics.failed_requests:
        tl = req.total_latency
        qw = req.queue_wait_time
        writer.writerow({
            "id":               req.id,
            "request_type":     req.request_type,
            "status":           req.status.value,
            "created_at":       req.created_at,
            "total_latency_ms": round(tl * 1000, 4) if tl is not None else "",
            "queue_wait_ms":    round(qw * 1000, 4) if qw is not None else "",
            "timed_out":        req.timed_out,
            "path":             ">".join(req.path),
        })
    return buf.getvalue().encode()
