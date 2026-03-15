from __future__ import annotations
import heapq
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from simulator.architecture import Architecture
from simulator.engine import SimulationEngine
from simulator.metrics import Metrics
from traffic.generators import burst_arrivals, poisson_arrivals
from backend.models import SimulateRequest, SimulateResponse

app = FastAPI(title="NetworkSim API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health():
    return {"status": "ok"}


@app.get("/api/presets")
def presets():
    cfg_path = Path(__file__).parent.parent / "configs" / "default_architectures.json"
    return json.loads(cfg_path.read_text())["architectures"]


@app.post("/api/simulate", response_model=SimulateResponse)
def simulate(req: SimulateRequest):
    try:
        arch_cfg = {
            "name": "custom",
            "entry_node_id": req.entry_node_id,
            "nodes": [
                {
                    "id": n.id,
                    "name": n.name,
                    "capacity": n.capacity,
                    "mean_processing_time": n.mean_processing_time,
                    "std_processing_time": n.std_processing_time,
                    "failure_rate": n.failure_rate,
                    "hit_rate": n.hit_rate,
                    "timeout": n.timeout,
                    "processing_profiles": n.processing_profiles,
                    "fan_out": n.fan_out,
                }
                for n in req.nodes
            ],
            "edges": [list(e) for e in req.edges],
            "routing": req.routing,
            "link_latency": [list(t) for t in req.link_latency],
        }

        arch    = Architecture.from_dict(arch_cfg)
        metrics = Metrics()
        engine  = SimulationEngine(arch, metrics)

        for n in req.nodes:
            for o in n.outages:
                engine.schedule_outage(n.id, o.start, o.duration)

        if req.burst:
            events = burst_arrivals(
                rate=req.rate,
                duration=req.duration,
                entry_node_id=arch.entry_node_id,
                burst_start=req.burst.start,
                burst_end=req.burst.end,
                burst_multiplier=req.burst.multiplier,
                seed=req.seed,
            )
        else:
            events = poisson_arrivals(
                rate=req.rate,
                duration=req.duration,
                entry_node_id=arch.entry_node_id,
                seed=req.seed,
            )

        for ev in events:
            heapq.heappush(engine._heap, (ev.time, engine._counter, ev))
            engine._counter += 1

        engine.run(until=req.duration)
        return SimulateResponse(summary=metrics.summary())

    except KeyError as e:
        raise HTTPException(status_code=422, detail=f"Invalid architecture: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
