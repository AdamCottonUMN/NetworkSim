from __future__ import annotations
import random
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple

from .node import Node


class RoutingStrategy(Enum):
    FIRST       = "first"        # always take the first edge (default, deterministic)
    ROUND_ROBIN = "round_robin"  # cycle through edges evenly
    RANDOM      = "random"       # pick a random downstream node
    WEIGHTED    = "weighted"     # pick based on per-edge weights


@dataclass
class Architecture:
    """
    A directed graph of Nodes connected by Edges.

    Routing strategies
    ------------------
    Each source node can have its own RoutingStrategy. Set one with:

        arch.set_routing("lb", RoutingStrategy.ROUND_ROBIN)

    For WEIGHTED routing also supply weights:

        arch.set_routing("lb", RoutingStrategy.WEIGHTED,
                         weights={"app1": 0.7, "app2": 0.3})

    Weights don't need to sum to 1 — they're relative.
    """

    name: str
    nodes: Dict[str, Node] = field(default_factory=dict)
    edges: Dict[str, List[str]] = field(default_factory=dict)
    entry_node_id: Optional[str] = None

    # Per-link transit latency in seconds (populated from config or API request)
    link_latency: Dict[Tuple[str, str], float] = field(default_factory=dict)

    # Routing config (set via set_routing() or from_dict())
    _strategies: Dict[str, RoutingStrategy] = field(default_factory=dict, repr=False)
    _weights: Dict[str, Dict[str, float]] = field(default_factory=dict, repr=False)

    # Round-robin state (reset between runs)
    _rr_counters: Dict[str, int] = field(default_factory=dict, repr=False)

    # ---------------------------------------------------------------- building

    def add_node(self, node: Node) -> None:
        self.nodes[node.id] = node
        if self.entry_node_id is None:
            self.entry_node_id = node.id

    def add_edge(self, from_id: str, to_id: str) -> None:
        self.edges.setdefault(from_id, []).append(to_id)

    def set_routing(
        self,
        node_id: str,
        strategy: RoutingStrategy,
        weights: Optional[Dict[str, float]] = None,
    ) -> None:
        self._strategies[node_id] = strategy
        if weights:
            self._weights[node_id] = weights

    # ---------------------------------------------------------------- querying

    def get_node(self, node_id: str) -> Node:
        return self.nodes[node_id]

    def get_link_latency(self, from_id: str, to_id: str) -> float:
        """Return transit delay in seconds between two nodes (0.0 if unset)."""
        return self.link_latency.get((from_id, to_id), 0.0)

    def get_next_node(self, node_id: str) -> Optional[str]:
        """Route a request leaving `node_id` to one of its downstream nodes."""
        nexts = self.edges.get(node_id, [])
        if not nexts:
            return None
        if len(nexts) == 1:
            return nexts[0]

        strategy = self._strategies.get(node_id, RoutingStrategy.FIRST)

        if strategy == RoutingStrategy.ROUND_ROBIN:
            idx = self._rr_counters.get(node_id, 0)
            self._rr_counters[node_id] = (idx + 1) % len(nexts)
            return nexts[idx]

        if strategy == RoutingStrategy.RANDOM:
            return random.choice(nexts)

        if strategy == RoutingStrategy.WEIGHTED:
            weight_map = self._weights.get(node_id, {})
            weights = [weight_map.get(n, 1.0) for n in nexts]
            return random.choices(nexts, weights=weights)[0]

        # FIRST (default)
        return nexts[0]

    def reset(self) -> None:
        """Clear all node runtime state and routing counters for a fresh run."""
        for node in self.nodes.values():
            node.reset()
        self._rr_counters.clear()

    # ---------------------------------------------------------------- factories

    @classmethod
    def linear_chain(cls, name: str, node_configs: List[dict]) -> "Architecture":
        """
        Build a simple linear pipeline: node[0] → node[1] → … → node[n-1].

        Each dict maps to Node constructor kwargs.
        """
        arch = cls(name=name)
        prev_id: Optional[str] = None
        for cfg in node_configs:
            node = Node(**cfg)
            arch.add_node(node)
            if prev_id is not None:
                arch.add_edge(prev_id, node.id)
            prev_id = node.id
        return arch

    @classmethod
    def from_dict(cls, config: dict) -> "Architecture":
        """
        Build an architecture from a plain dict (e.g. loaded from JSON).

        Format::

            {
              "name": "my_arch",
              "entry_node_id": "lb",          # optional
              "nodes": [{"id": "lb", ...}, ...],
              "edges": [["lb", "app"], ...],
              "routing": {                     # optional
                "lb": {
                  "strategy": "round_robin"    # first|round_robin|random|weighted
                  "weights": {"app1": 2, "app2": 1}   # only for weighted
                }
              }
            }
        """
        arch = cls(name=config["name"])

        for node_cfg in config["nodes"]:
            arch.add_node(Node(**node_cfg))

        for from_id, to_id in config.get("edges", []):
            arch.add_edge(from_id, to_id)

        if config.get("entry_node_id"):
            arch.entry_node_id = config["entry_node_id"]

        for node_id, rcfg in config.get("routing", {}).items():
            strategy = RoutingStrategy(rcfg.get("strategy", "first"))
            weights = rcfg.get("weights")
            arch.set_routing(node_id, strategy, weights)

        for from_id, to_id, lat in config.get("link_latency", []):
            arch.link_latency[(from_id, to_id)] = lat

        return arch

    def __repr__(self) -> str:
        return f"Architecture(name={self.name!r}, nodes={list(self.nodes)}, edges={self.edges})"
