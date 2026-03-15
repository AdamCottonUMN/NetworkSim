"""
run_simulation.py — example entry point for the Network Architecture Simulator.

Runs three scenarios back-to-back and prints a side-by-side summary:
  1. simple_web_stack at normal load
  2. simple_web_stack at high load (bottleneck demo)
  3. cached_web_stack at high load (shows cache helping)
"""

import heapq
import json
from pathlib import Path

from simulator.architecture import Architecture
from simulator.engine import SimulationEngine
from simulator.metrics import Metrics
from traffic.generators import poisson_arrivals


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_architecture(name: str) -> Architecture:
    cfg_path = Path(__file__).parent / "configs" / "default_architectures.json"
    data = json.loads(cfg_path.read_text())
    arch_cfg = next(a for a in data["architectures"] if a["name"] == name)
    return Architecture.from_dict(arch_cfg)


def run(arch: Architecture, rate: float, duration: float, seed: int = 42) -> dict:
    """Run one simulation and return the summary dict."""
    arch.reset()
    metrics = Metrics()
    engine = SimulationEngine(arch, metrics)

    events = poisson_arrivals(
        rate=rate,
        duration=duration,
        entry_node_id=arch.entry_node_id,
        seed=seed,
    )
    for ev in events:
        heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
        engine._counter += 1

    engine.run(until=duration)
    return metrics.summary()


def print_summary(label: str, s: dict) -> None:
    bar = "=" * 55
    print(f"\n{bar}")
    print(f"  {label}")
    print(f"{bar}")
    print(f"  Total requests : {s['total_requests']}")
    print(f"  Completed      : {s['completed']}")
    print(f"  Failed         : {s['failed']}  ({s['failure_rate']:.1%})")
    print(f"  Avg latency    : {s['avg_latency_ms']:.1f} ms")
    print(f"  p50 latency    : {s['p50_latency_ms']:.1f} ms")
    print(f"  p95 latency    : {s['p95_latency_ms']:.1f} ms")
    print(f"  p99 latency    : {s['p99_latency_ms']:.1f} ms")
    print()
    print(f"  {'Node':<20} {'Util':>6}  {'Avg Q':>6}  {'Max Q':>6}  {'Fail':>6}")
    print(f"  {'-'*20} {'-'*6}  {'-'*6}  {'-'*6}  {'-'*6}")
    for nid, nm in s["node_metrics"].items():
        print(
            f"  {nid:<20} "
            f"{nm['avg_utilization']:>6.1%}  "
            f"{nm['avg_queue_size']:>6.1f}  "
            f"{nm['max_queue_size']:>6}  "
            f"{nm['failures']:>6}"
        )


# ---------------------------------------------------------------------------
# Scenarios
# ---------------------------------------------------------------------------

DURATION = 60.0   # seconds of simulated time

def main():
    print("\n=== Network Architecture Simulator ===")

    # Scenario 1: normal load
    arch = load_architecture("simple_web_stack")
    s1 = run(arch, rate=20, duration=DURATION)
    print_summary("simple_web_stack  |  20 req/s  (normal load)", s1)

    # Scenario 2: high load — DB becomes the bottleneck
    arch = load_architecture("simple_web_stack")
    s2 = run(arch, rate=80, duration=DURATION)
    print_summary("simple_web_stack  |  80 req/s  (high load — DB bottleneck)", s2)

    # Scenario 3: cached stack at the same high load
    arch = load_architecture("cached_web_stack")
    s3 = run(arch, rate=80, duration=DURATION)
    print_summary("cached_web_stack  |  80 req/s  (cache in front of DB)", s3)


if __name__ == "__main__":
    main()
