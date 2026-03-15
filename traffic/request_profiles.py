"""
Named request profiles — pre-defined parameter sets for common workload types.

Each profile is a dict that can be passed directly to a generator function
or used to configure a batch of requests.

Usage
-----
from traffic.request_profiles import PROFILES
from traffic.generators import poisson_arrivals

profile = PROFILES["read_heavy"]
events = poisson_arrivals(
    rate=profile["rate"],
    duration=60.0,
    entry_node_id="lb",
    request_type=profile["request_type"],
)
"""

from __future__ import annotations
from typing import Any, Dict

PROFILES: Dict[str, Dict[str, Any]] = {
    "baseline": {
        "request_type": "http",
        "rate": 10,           # req/s
        "description": "Light background load for smoke-testing",
    },
    "read_heavy": {
        "request_type": "read",
        "rate": 100,
        "description": "High-volume read traffic (CDN / cached endpoints)",
    },
    "write_heavy": {
        "request_type": "write",
        "rate": 40,
        "description": "Write-intensive workload (e.g. ingest pipeline)",
    },
    "spike": {
        "request_type": "http",
        "rate": 500,
        "description": "Short-lived traffic spike (flash sale / viral event)",
    },
    "batch_job": {
        "request_type": "batch",
        "rate": 5,
        "description": "Slow, large requests (report generation / ETL)",
    },
}


def get_profile(name: str) -> Dict[str, Any]:
    """Return a named profile, raising KeyError with helpful message if missing."""
    if name not in PROFILES:
        available = ", ".join(PROFILES)
        raise KeyError(f"Unknown profile {name!r}. Available: {available}")
    return PROFILES[name]
