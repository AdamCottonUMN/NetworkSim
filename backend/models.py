from __future__ import annotations
from pydantic import BaseModel


class OutageConfig(BaseModel):
    start: float
    duration: float


class NodeConfig(BaseModel):
    id: str
    name: str
    node_type: str = "generic"     # frontend visual type only, not passed to simulator
    capacity: int = 10
    mean_processing_time: float = 0.05
    std_processing_time: float = 0.01
    failure_rate: float = 0.0
    hit_rate: float = 0.0
    timeout: float | None = None
    processing_profiles: dict = {}
    fan_out: bool = False
    outages: list[OutageConfig] = []


class BurstConfig(BaseModel):
    start: float
    end: float
    multiplier: float


class SimulateRequest(BaseModel):
    nodes: list[NodeConfig]
    edges: list[tuple[str, str]]
    entry_node_id: str
    routing: dict = {}
    link_latency: list[tuple[str, str, float]] = []   # [from_id, to_id, seconds]
    rate: float = 50
    duration: float = 60
    seed: int = 42
    burst: BurstConfig | None = None


class SimulateResponse(BaseModel):
    summary: dict
    sla: dict | None = None
